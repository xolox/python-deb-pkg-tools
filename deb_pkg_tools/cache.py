# Debian packaging tools: Caching of package metadata.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: April 18, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Debian binary package metadata cache.

The :class:`PackageCache` class implements a persistent, multiprocess cache for
Debian binary package metadata. The cache supports the following binary package
metadata:

- The control fields of packages;
- The files installed by packages;
- The MD5, SHA1 and SHA256 sums of packages.

The package metadata cache can speed up the following functions:

- :func:`.collect_related_packages()`
- :func:`.get_packages_entry()`
- :func:`.inspect_package()`
- :func:`.inspect_package_contents()`
- :func:`.inspect_package_fields()`
- :func:`.scan_packages()`
- :func:`.update_repository()`

Because a lot of functionality in `deb-pkg-tools` uses
:func:`.inspect_package()` and its variants, the package metadata cache
almost always provides a speedup compared to recalculating metadata on demand.

The cache is especially useful when you're manipulating large package
repositories where relatively little metadata changes (which is a pretty common
use case if you're using `deb-pkg-tools` seriously).

Internals
---------

For several years the package metadata cache was based on SQLite and this
worked fine. Then I started experimenting with concurrent builds on the same
build server and I ran into SQLite raising lock timeout errors. I switched
SQLite to use the Write-Ahead Log (WAL) and things seemed to improve until
I experienced several corrupt databases in situations where multiple writers
and multiple readers were all hitting the cache at the same time.

At this point I looked around for alternative cache backends with the following
requirements:

- Support for concurrent reading and writing without any locking or blocking.

- It should not be possible to corrupt the cache, regardless of concurrency.

- To keep system requirements to a minimum, it should not be required to have
  a server (daemon) process running just for the cache to function.

These conflicting requirements left me with basically no options :-). Based on
previous good experiences I decided to try using the filesystem to store the
cache, with individual files representing cache entries. Through atomic
filesystem operations this strategy basically delegates all locking to the
filesystem, which should be guaranteed to do the right thing (POSIX).

Storing the cache on the filesystem like this has indeed appeared to solve all
locking and corruption issues, but when the filesystem cache is cold (for
example because you've just run a couple of heavy builds) it's still damn slow
to scan the package metadata of a full repository with hundreds of archives...

As a pragmatic performance optimization :man:`memcached` was added to the mix.
Any errors involving memcached are silently ignored which means memcached isn't
required to use the cache; it's an optional optimization.
"""

# Standard library modules.
import errno
import glob
import logging
import os
import time

# External dependencies.
from humanfriendly import Timer, format_timespan
from humanfriendly.decorators import cached
from humanfriendly.text import pluralize
from six.moves import cPickle as pickle

# Modules included in our package.
from deb_pkg_tools.utils import makedirs, sha1

# Public identifiers that require documentation.
__all__ = (
    "CACHE_FORMAT_REVISION",
    "CacheEntry",
    "PackageCache",
    "get_default_cache",
    "logger",
)

CACHE_FORMAT_REVISION = 2
"""The version number of the cache format (an integer)."""

# Initialize a logger for this module.
logger = logging.getLogger(__name__)


@cached
def get_default_cache():
    """
    Load the default package cache stored inside the user's home directory.

    The location of the cache is configurable using the option
    :data:`.package_cache_directory`, however make sure you set that option
    *before* calling :func:`get_default_cache()` because the cache will be
    initialized only once.

    :returns: A :class:`PackageCache` object.
    """
    from deb_pkg_tools.config import package_cache_directory
    return PackageCache(directory=package_cache_directory)


class PackageCache(object):

    """A persistent, multiprocess cache for Debian binary package metadata."""

    def __init__(self, directory):
        """
        Initialize a package cache.

        :param directory: The pathname of the package cache directory (a string).
        """
        self.directory = directory
        self.entries = {}
        self.connect_memcached()

    def __getstate__(self):
        """
        Save a :mod:`pickle` compatible :class:`PackageCache` representation.

        The :func:`__getstate__()` and :func:`__setstate__()` methods make
        :class:`PackageCache` objects compatible with :mod:`multiprocessing`
        (which uses :mod:`pickle`). This capability is used by
        :func:`deb_pkg_tools.cli.collect_packages()` to
        enable concurrent package collection.
        """
        # Get what is normally pickled.
        state = self.__dict__.copy()
        # Avoid pickling the `entries' and `memcached' attributes.
        state.pop('entries')
        state.pop('memcached', None)
        # Pickle the other attributes.
        return state

    def __setstate__(self, state):
        """Load a :mod:`pickle` compatible :class:`PackageCache` representation."""
        self.__dict__.update(state)
        self.entries = {}
        self.connect_memcached()

    def connect_memcached(self):
        """Initialize a connection to the memcached daemon."""
        try:
            module = __import__('memcache')
            self.memcached = module.Client(['127.0.0.1:11211'])
        except Exception:
            self.use_memcached = False
        else:
            self.use_memcached = True

    def get_entry(self, category, pathname):
        """
        Get an object representing a cache entry.

        :param category: The type of metadata that this cache entry represents
                         (a string like 'control-fields', 'package-fields' or
                         'contents').
        :param pathname: The pathname of the package archive (a string).
        :returns: A :class:`CacheEntry` object.
        """
        # Normalize the pathname so we can use it as a dictionary & cache key.
        pathname = os.path.abspath(pathname)
        # Check if the entry was previously initialized.
        key = (category, pathname)
        entry = self.entries.get(key)
        if not entry:
            # Initialize a new entry.
            entry = CacheEntry(self, category, pathname)
            self.entries[key] = entry
        return entry

    def collect_garbage(self, force=False, interval=60 * 60 * 24):
        """
        Delete any entries in the persistent cache that refer to deleted archives.

        :param force: :data:`True` to force a full garbage collection run
                      (defaults to :data:`False` which means garbage collection
                      is performed only once per `interval`).
        :param interval: The number of seconds to delay garbage collection when
                         `force` is :data:`False` (a number, defaults to the
                         equivalent of 24 hours).
        """
        timer = Timer()
        num_checked = 0
        num_deleted = 0
        marker_file = os.path.join(self.directory, 'last-gc.txt')
        if not os.path.isdir(self.directory):
            logger.debug("Skipping garbage collection (cache directory doesn't exist).")
            return
        elif force:
            logger.info("Performing forced garbage collection ..")
        else:
            # Check whether garbage collection is needed, the idea being that
            # garbage collection can be expensive (given enough cache entries
            # and/or a cold enough disk cache) so we'd rather not do it when
            # it's not necessary.
            logger.debug("Checking whether garbage collection is necessary ..")
            try:
                last_gc = os.path.getmtime(marker_file)
            except Exception:
                last_gc = 0
            elapsed_time = time.time() - last_gc
            logger.debug("Elapsed time since last garbage collection: %s",
                         format_timespan(elapsed_time))
            if elapsed_time < interval:
                logger.debug("Skipping automatic garbage collection (elapsed time < interval).")
                return
            else:
                logger.debug("Performing automatic garbage collection (elapsed time > interval).")
        for cache_file in glob.glob(os.path.join(self.directory, '*', '*.pickle')):
            try:
                with open(cache_file, 'rb') as handle:
                    data = pickle.load(handle)
                last_modified = os.path.getmtime(data['pathname'])
                is_garbage = (last_modified != data['last_modified'])
            except Exception:
                is_garbage = True
            if is_garbage:
                try:
                    os.unlink(cache_file)
                    num_deleted += 1
                except EnvironmentError as e:
                    # Silence `No such file or directory' errors (e.g. due to
                    # concurrent garbage collection runs) without accidentally
                    # swallowing other exceptions (that we don't know how to
                    # handle).
                    if e.errno != errno.ENOENT:
                        raise
            num_checked += 1
        # Record when garbage collection was last run.
        with open(marker_file, 'a') as handle:
            os.utime(marker_file, None)
        status_level = logging.INFO if force else logging.DEBUG
        if num_checked == 0:
            logger.log(status_level, "Nothing to garbage collect (the cache is empty).")
        else:
            logger.log(status_level, "Checked %s, garbage collected %s in %s.",
                       pluralize(num_checked, "cache entry", "cache entries"),
                       pluralize(num_deleted, "cache entry", "cache entries"),
                       timer)


class CacheEntry(object):

    """An entry in the package metadata cache provided by :class:`PackageCache`."""

    def __init__(self, cache, category, pathname):
        """
        Initialize a :class:`CacheEntry` object.

        :param cache: The :class:`PackageCache` that created this entry.
        :param category: The type of metadata that this cache entry represents
                         (a string like 'control-fields', 'package-fields' or
                         'contents').
        :param pathname: The pathname of the package archive (a string).
        """
        # Store the arguments.
        self.cache = cache
        self.category = category
        self.pathname = pathname
        # Generate the entry's cache key and filename.
        fingerprint = sha1(pathname)
        self.cache_key = 'deb-pkg-tools:%s:%s' % (category, fingerprint)
        self.cache_file = os.path.join(self.cache.directory, category, '%s.pickle' % fingerprint)
        # Get the archive's last modified time.
        self.last_modified = os.path.getmtime(pathname)
        # Prepare to cache the value in memory.
        self.in_memory = None

    def get_value(self):
        """
        Get the cache entry's value.

        :returns: A previously cached value or :data:`None` (when the value
                  isn't available in the cache).
        """
        # Check for a value that was previously cached in memory.
        if self.up_to_date(self.in_memory):
            return self.in_memory['value']
        # Check for a value that was previously cached in memcached.
        if self.cache.use_memcached:
            try:
                from_mc = self.cache.memcached.get(self.cache_key)
                if self.up_to_date(from_mc):
                    # Cache the value in memory.
                    self.in_memory = from_mc
                    return from_mc['value']
            except Exception:
                pass
        # Check for a value that was previously cached on the filesystem.
        try:
            with open(self.cache_file, 'rb') as handle:
                from_fs = pickle.load(handle)
            if self.up_to_date(from_fs):
                # Cache the value in memory and in memcached.
                self.in_memory = from_fs
                self.set_memcached()
                return from_fs['value']
        except Exception:
            pass

    def set_value(self, value):
        """
        Set the cache entry's value.

        :param value: The metadata to save in the cache.
        """
        # Cache the value in memory.
        self.in_memory = dict(
            last_modified=self.last_modified,
            pathname=self.pathname,
            revision=CACHE_FORMAT_REVISION,
            value=value,
        )
        # Cache the value in memcached.
        self.set_memcached()
        # Cache the value on the filesystem.
        directory, filename = os.path.split(self.cache_file)
        temporary_file = os.path.join(directory, '.%s-%i' % (filename, os.getpid()))
        try:
            # Try to write the cache file.
            self.write_file(temporary_file)
        except EnvironmentError as e:
            # We may be missing the cache directory.
            if e.errno == errno.ENOENT:
                # Make sure the cache directory exists.
                makedirs(directory)
                # Try to write the cache file again.
                self.write_file(temporary_file)
            else:
                # Don't swallow exceptions we can't handle.
                raise
        # Move the temporary file into place, trusting the
        # filesystem to handle this operation atomically.
        os.rename(temporary_file, self.cache_file)

    def set_memcached(self):
        """Helper for :func:`get_value()` and :func:`set_value()` to write to memcached."""
        if self.cache.use_memcached:
            try:
                self.cache.memcached.set(self.cache_key, self.in_memory)
            except Exception:
                self.cache.use_memcached = False

    def up_to_date(self, value):
        """Helper for :func:`get_value()` to validate cached values."""
        return (value and
                value['pathname'] == self.pathname and
                value['last_modified'] >= self.last_modified and
                value.get('revision') == CACHE_FORMAT_REVISION)

    def write_file(self, filename):
        """Helper for :func:`set_value()` to cache values on the filesystem."""
        with open(filename, 'wb') as handle:
            pickle.dump(self.in_memory, handle)
