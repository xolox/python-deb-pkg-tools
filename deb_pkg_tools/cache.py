# Debian packaging tools: Caching of package metadata.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: February 26, 2015
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Package metadata cache
======================

The :py:class:`PackageCache` class implements a persistent, multiprocess cache
for Debian binary package metadata using :py:mod:`sqlite3`. The cache supports
the following binary package metadata:

- The control fields of packages;
- The files installed by packages;
- The MD5, SHA1 and SHA256 sums of packages.

The package metadata cache can speed up the following functions:

- :py:func:`.collect_related_packages()`
- :py:func:`.get_packages_entry()`
- :py:func:`.inspect_package()`
- :py:func:`.inspect_package_contents()`
- :py:func:`.inspect_package_fields()`
- :py:func:`.scan_packages()`
- :py:func:`.update_repository()`

Because a lot of functionality in `deb-pkg-tools` uses
:py:func:`.inspect_package()` and its variants, the package metadata cache
almost always provides a speedup compared to recalculating metadata on demand.
The cache is especially useful when you're manipulating large package
repositories where relatively little metadata changes (which is a pretty common
use case if you're using `deb-pkg-tools` seriously).
"""

# Standard library modules.
import codecs
import logging
import os
import sqlite3
import zlib

# Load the fastest pickle module available to us.
try:
    import cPickle as pickle
except ImportError:
    import pickle

# External dependencies.
from cached_property import cached_property
from humanfriendly import Timer

# Modules included in our package.
from deb_pkg_tools.package import inspect_package_contents, inspect_package_fields
from deb_pkg_tools.repo import get_packages_entry
from deb_pkg_tools.utils import atomic_lock, makedirs

# Initialize a logger for this module.
logger = logging.getLogger(__name__)

# Instance of PackageCache, initialized on demand by get_default_cache().
default_cache_instance = None

def get_default_cache():
    """
    Load the default package cache stored inside the user's home directory.

    The location of the cache is configurable using the option
    :py:data:`.package_cache_file`, however make sure you set that option
    *before* calling :py:func:`get_default_cache()` because the cache will be
    initialized only once.

    :returns: A :py:class:`PackageCache` object.
    """
    global default_cache_instance
    if default_cache_instance is None:
        from deb_pkg_tools.config import package_cache_file
        default_cache_instance = PackageCache(filename=os.path.expanduser(package_cache_file))
    return default_cache_instance

class PackageCache(object):

    """
    A persistent, multi process cache for Debian binary package metadata.
    """

    def __init__(self, filename):
        """
        Initialize a package cache.

        :param filename: The pathname of the SQLite database file (a string).
        """
        self.character_encoding = 'utf-8'
        self.db = None
        self.db_timer = Timer(resumable=True)
        self.decode_timer = Timer(resumable=True)
        self.encode_timer = Timer(resumable=True)
        self.filename = os.path.expanduser(filename)
        self.fs_timer = Timer(resumable=True)
        self.gc_enabled = False
        self.gc_timer = Timer(resumable=True)
        self.identity_map = {}

    def initialize(self):
        """
        Initialize (create and/or upgrade) the package cache database.
        """
        if self.db is None:
            # Create any missing directories.
            makedirs(os.path.dirname(self.filename))
            with atomic_lock(self.filename):
                # Open the SQLite database connection, enable autocommit.
                self.db = sqlite3.connect(database=self.filename, isolation_level=None)
                # Initialize the database schema.
                self.upgrade_schema(1, '''
                    create table package_cache (
                        pathname text primary key,
                        timestamp real not null,
                        control_fields blob null,
                        package_fields blob null,
                        contents blob null
                    );
                ''')
            # Enable 8-bit bytestrings so we can store binary data.
            try:
                # Python 3.x.
                self.db.text_factory = bytes
            except NameError:
                # Python 2.x.
                self.db.text_factory = str
            # Use a custom row factory to implement lazy evaluation. Previously
            # this used functools.partial() to inject self (a PackageCache
            # object) into the CachedPackage constructor, however as of Python
            # 3.4.2 this causes the following error to be raised:
            #
            #   TypeError: Row() does not take keyword arguments
            #   https://travis-ci.org/xolox/python-deb-pkg-tools/jobs/44186883#L746
            #
            # Looks like this was caused by the changes referenced in
            # http://bugs.python.org/issue21975.
            class CachedPackagePartial(CachedPackage):
                cache = self
            self.db.row_factory = CachedPackagePartial

    def upgrade_schema(self, version, script):
        """
        Upgrade the database schema on demand.

        :param version: The version to upgrade to (an integer).
        :param script: The SQL statement(s) to upgrade the schema (a string).
        """
        # Get the version of the database schema.
        # http://www.sqlite.org/pragma.html#pragma_schema_version
        cursor = self.execute('pragma user_version')
        existing_version = cursor.fetchone()[0]
        if existing_version < version:
            logger.debug("Upgrading database schema from %i to %i ..", existing_version, version)
            self.db.executescript(script)
            self.execute('pragma user_version = %d' % version)

    def collect_garbage(self, force=False):
        """
        Cleanup expired cache entries.
        """
        if self.gc_enabled or force:
            self.initialize()
            with self.gc_timer:
                select_cursor = self.db.cursor()
                delete_cursor = self.db.cursor()
                logger.debug("Garbage collecting expired cache entries ..")
                for package in select_cursor.execute('select pathname, timestamp from package_cache'):
                    try:
                        with self.fs_timer:
                            assert package.timestamp == os.path.getmtime(package.pathname)
                    except Exception:
                        with self.db_timer:
                            delete_cursor.execute('delete from package_cache where pathname = ?', (package.pathname,))
                self.gc_enabled = False
        self.dump_stats()

    def dump_stats(self):
        """
        Write database statistics to the log stream.
        """
        logger.debug("Package cache statistics:"
                + "\n - Spent %s on database I/O." % self.db_timer
                + "\n - Spent %s on garbage collection." % self.gc_timer
                + "\n - Spent %s on getmtime() calls." % self.fs_timer
                + "\n - Spent %s on value encoding." % self.encode_timer
                + "\n - Spent %s on value decoding." % self.decode_timer)

    def __getitem__(self, pathname):
        """
        Get a Debian binary package archive's metadata from the cache.

        :param pathname: The pathname of a Debian binary package archive (a string).
        :returns: A :py:class:`CachedPackage` object.
        :raises: :py:exc:`KeyError` when the Debian binary package archive doesn't exist.
        """
        self.initialize()
        # Make sure the package archive exists on disk.
        with self.fs_timer:
            try:
                pathname = os.path.realpath(pathname)
                timestamp = os.path.getmtime(pathname)
                key = pathname.encode(self.character_encoding)
            except OSError:
                msg = "Debian binary package archive doesn't exist! (%s)"
                raise KeyError(msg % pathname)
        # Get the package object from the identity map but fall back to
        # the database if the object in the identity map is outdated.
        package = self.identity_map.get(key)
        if not (package and package.timestamp == timestamp):
            select_query = 'select * from package_cache where pathname = ? and timestamp = ?'
            cursor = self.execute(select_query, key, timestamp)
            self.identity_map[key] = cursor.fetchone()
        # Invalidate the cached package (if any) and create a new one?
        package = self.identity_map.get(key)
        if not (package and package.timestamp == timestamp):
            self.execute('''
                replace into package_cache (pathname, timestamp, control_fields, package_fields, contents)
                values (?, ?, null, null, null)
            ''', key, timestamp)
            # Get the new cache entry.
            select_query = 'select * from package_cache where pathname = ?'
            cursor = self.execute(select_query, key)
            self.identity_map[key] = cursor.fetchone()
        # Always return an object from the identity map.
        return self.identity_map[key]

    def execute(self, query, *params):
        """
        Execute a query.

        :param query: The SQL query to execute (a string).
        :param params: Zero or more substitution parameters (a tuple).
        :returns: An :py:class:`sqlite3.Cursor` object.
        """
        with self.db_timer:
            tokens = query.split()
            query = ' '.join(tokens)
            cursor = self.db.execute(query, params)
            if tokens[0] != 'select':
                self.gc_enabled = True
            return cursor

    def encode(self, python_value):
        """
        Encode a Python value so it can be stored in the cache.

        :param python_value: Any Python value that can be pickled.
        """
        with self.encode_timer:
            pickled_data = pickle.dumps(python_value, pickle.HIGHEST_PROTOCOL)
            compressed_data = zlib.compress(pickled_data)
            return sqlite3.Binary(compressed_data)

    def decode(self, database_value):
        """
        Decode a value that was previously encoded with :py:func:`encode()`.

        :param database_value: An encoded Python value (a string).
        """
        with self.decode_timer:
            return pickle.loads(zlib.decompress(database_value))

class CachedPackage(sqlite3.Row):

    """
    Custom SQLite row factory that implements lazy evaluation.

    The following attributes are always available:

    - :py:attr:`pathname`
    - :py:attr:`timestamp`

    The following attributes are loaded on demand:

    - :py:attr:`control_fields`
    - :py:attr:`package_fields`
    - :py:attr:`contents`
    """

    @cached_property
    def pathname(self):
        """
        Get the pathname of the Debian binary package archive.

        :returns: The pathname (a string).
        """
        # Due to our use of text_factory, self['pathname'] is a buffer object in
        # Python 2.x and a bytes object in Python 3.x. The buffer object will
        # not have a decode() method so we use codecs.decode() as a `universal
        # method' avoiding a dedicated code path for Python 2.x vs 3.x.
        return codecs.decode(self['pathname'], self.cache.character_encoding)

    @property
    def timestamp(self):
        """
        Get the last modified time of the Debian binary package archive.

        :returns: The last modified time (a float).
        """
        return self['timestamp']

    @cached_property
    def control_fields(self):
        """
        The control fields extracted from the Debian binary package archive.

        :returns: A dictionary with control fields generated by
                  :py:func:`.inspect_package_fields()`.
        """
        if self['control_fields']:
            try:
                return self.cache.decode(self['control_fields'])
            except Exception as e:
                logger.warning("Failed to load cached control fields of %s! (%s)", self.pathname, e)
        control_fields = inspect_package_fields(self.pathname)
        update_query = 'update package_cache set control_fields = ? where pathname = ?'
        self.cache.execute(update_query, self.cache.encode(control_fields), self.pathname)
        return control_fields

    @cached_property
    def package_fields(self):
        """
        The control fields required in a ``Packages`` file.

        :returns: A dictionary with control fields generated by
                  :py:func:`.get_packages_entry()`.
        """
        if self['package_fields']:
            try:
                return self.cache.decode(self['package_fields'])
            except Exception as e:
                logger.warning("Failed to load cached package fields of %s! (%s)", self.pathname, e)
        package_fields = get_packages_entry(self.pathname)
        update_query = 'update package_cache set package_fields = ? where pathname = ?'
        self.cache.execute(update_query, self.cache.encode(package_fields), self.pathname)
        return package_fields

    @cached_property
    def contents(self):
        """
        The contents extracted from the Debian binary package archive (a dictionary).

        :returns: A dictionary with package contents just like the one returned
                  by :py:func:`.inspect_package_contents()`.
        """
        if self['contents']:
            try:
                return self.cache.decode(self['contents'])
            except Exception as e:
                logger.warning("Failed to load cached contents of %s! (%s)", self.pathname, e)
        contents = inspect_package_contents(self.pathname)
        update_query = 'update package_cache set contents = ? where pathname = ?'
        self.cache.execute(update_query, self.cache.encode(contents), self.pathname)
        return contents

# vim: ts=4 sw=4 et
