# Debian packaging tools: Trivial repository management.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: June 1, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Repository management
=====================

The functions in the :py:mod:`deb_pkg_tools.repo` module make it possible to
transform a directory of ``*.deb`` archives into a (temporary) Debian package
repository:

- :py:func:`update_repository()` creates/updates a `trivial repository`_

- :py:func:`activate_repository()` enables ``apt-get`` to install packages from
  the trivial repository

- :py:func:`deactivate_repository()` cleans up after
  :py:func:`activate_repository()`

All of the functions in this module can raise :py:exc:`executor.ExternalCommandFailed`.

You can configure the GPG key(s) used by this module through a configuration
file, please refer to the documentation of :py:func:`select_gpg_key()`.

.. _trivial repository: http://www.debian.org/doc/manuals/repository-howto/repository-howto#id443677
"""

# Standard library modules.
import fnmatch
import functools
import hashlib
import json
import logging
import os.path
import pipes
import re
import shutil
import tempfile

# Python 2/3 compatibility.
try:
    import ConfigParser as configparser
except ImportError:
    import configparser

# External dependencies.
from executor import execute, ExternalCommandFailed
from humanfriendly import concatenate, format_path, Spinner, Timer

# Modules included in our package.
from deb_pkg_tools import config
from deb_pkg_tools.control import unparse_control_fields
from deb_pkg_tools.gpg import GPGKey, initialize_gnupg
from deb_pkg_tools.package import inspect_package_fields, find_package_archives
from deb_pkg_tools.utils import atomic_lock, sha1

# Initialize a logger.
logger = logging.getLogger(__name__)

class scan_packages(object):

    """
    A reimplementation of the ``dpkg-scanpackages -m`` command in Python that
    caches package archive metadata and hashes on disk to speed things up
    significantly. The location of the cache is currently hard coded as
    :py:data:`deb_pkg_tools.package_cache_file`.

    .. note:: This implementation currently uses an exclusive lock on the
              package cache file so that only one process can update the cache
              at the same time. Serializing all ``Packages`` file generation
              may not sound like the smartest idea, but given the speedup that
              :py:class:`scan_packages()` gives it's more than worth it.
    """

    def __init__(self, repository, packages_file=None):
        """
        Update a ``Packages`` file based on the Debian package archives found
        in the given directory. Raises :py:exc:`deb_pkg_tools.utils.ResourceLockedException`
        when another process is currently using the package cache.

        :param repository: The pathname of a directory containing Debian
                           package archives (a string).
        :param packages_file: The pathname of the ``Packages`` file to update
                              (a string). Defaults to the ``Packages`` file in
                              the given directory.
        """
        with atomic_lock(config.package_cache_file):
            # Initialize internal state.
            self.load_cache()
            # By default the `Packages' file inside the repository is updated.
            if not packages_file:
                packages_file = os.path.join(repository, 'Packages')
            # Update the `Packages' file.
            num_packages = 0
            timer = Timer()
            spinner = Spinner("Scanning package metadata ..")
            with open(packages_file, 'w') as handle:
                for archive in find_package_archives(repository):
                    fields = self.find_in_cache(archive.filename)
                    unparse_control_fields(fields).dump(handle)
                    handle.write('\n')
                    spinner.step()
                    num_packages += 1
            spinner.clear()
            # Save the updated cache to disk.
            self.save_cache()
            logger.debug("Wrote %i entries to output Packages file in %s.", num_packages, timer)

    def load_cache(self):
        """
        Load the package archive cache from disk.
        """
        timer = Timer()
        try:
            with open(config.package_cache_file) as handle:
                self.packages = json.load(handle)
                logger.debug("Loaded %i cached package(s) from %s in %s.", len(self.packages), format_path(config.package_cache_file), timer)
        except Exception:
            logger.debug("Failed to load package cache from disk (probably it wasn't initialized yet).")
            self.packages = {}

    def save_cache(self):
        """
        Save the package archive cache to disk.
        """
        self.collect_garbage()
        with open(config.package_cache_file, 'w') as handle:
            logger.debug("Saving %i cached package(s) to %s ..", len(self.packages), format_path(config.package_cache_file))
            json.dump(self.packages, handle)

    def collect_garbage(self):
        """
        Remove cache entries referring to non existing package archives.
        """
        garbage = []
        for filename in self.packages.keys():
            if not os.path.isfile(filename):
                garbage.append(filename)
        for filename in garbage:
            del self.packages[filename]

    def find_in_cache(self, filename):
        """
        Find the ``Packages`` file entry for the given Debian package archive.

        :param filename: The pathname of a Debian package archive (a string).
        :returns: A dictionary of control file and ``Packages`` file fields.
        """
        # Normalize the filename so we can use it as a dictionary key.
        filename = os.path.realpath(filename)
        # Find the package archive's last modified time.
        last_modified = os.path.getmtime(filename)
        # Check if the package archive was previously cached and if so
        # then make sure the cached data has not been invalidated.
        metadata = self.packages.get(filename, {})
        if metadata.get('last-modified') != last_modified:
            # Get the control file fields.
            fields = dict(unparse_control_fields(inspect_package_fields(filename)))
            fields['Version'] = str(fields['Version'])
            fields['Filename'] = os.path.basename(filename)
            fields['Size'] = str(os.path.getsize(filename))
            # Prepare to calculate the MD5, SHA1 and SHA256 hashes of the archive.
            md5_sum = hashlib.md5()
            sha1_sum = hashlib.sha1()
            sha256_sum = hashlib.sha256()
            # Read the file once in blocks, calculating all hashes at once.
            with open(filename) as handle:
                for chunk in iter(functools.partial(handle.read, 1024), ''):
                    md5_sum.update(chunk)
                    sha1_sum.update(chunk)
                    sha256_sum.update(chunk)
            # Store the hashes with the control file fields.
            fields['MD5sum'] = md5_sum.hexdigest()
            fields['SHA1'] = sha1_sum.hexdigest()
            fields['SHA256'] = sha256_sum.hexdigest()
            # Store the control file fields in the cache.
            metadata['control-fields'] = fields
            metadata['last-modified'] = last_modified
            self.packages[filename] = metadata
        return metadata['control-fields']

def update_repository(directory, release_fields={}, gpg_key=None):
    """
    Create or update a `trivial repository`_ using the Debian commands
    ``dpkg-scanpackages`` (reimplemented as :py:class:`scan_packages()`) and
    ``apt-ftparchive`` (also uses the external programs ``gpg`` and
    ``gzip``).  Raises :py:exc:`deb_pkg_tools.utils.ResourceLockedException`
    when the given repository directory is being updated by another process.

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param release_fields: An optional dictionary with fields to set inside the
                           ``Release`` file.
    :param gpg_key: The :py:class:`deb_pkg_tools.gpg.GPGKey` object used to
                    sign the repository. Defaults to the result of
                    :py:func:`select_gpg_key()`.
    """
    with atomic_lock(directory):
        timer = Timer()
        gpg_key = gpg_key or select_gpg_key(directory)
        # Figure out when the repository contents were last updated.
        contents_last_updated = os.path.getmtime(directory)
        for archive in find_package_archives(directory):
            contents_last_updated = max(contents_last_updated, os.path.getmtime(archive.filename))
        # Figure out when the repository metadata was last updated.
        try:
            metadata_files = ['Packages', 'Packages.gz', 'Release']
            # XXX If 1) no GPG key was provided, 2) apt doesn't require the
            # repository to be signed and 3) `Release.gpg' doesn't exist, it should
            # not cause an unnecessary repository update. That would turn the
            # conditional update into an unconditional update, which is not the
            # intention here :-)
            if os.path.isfile(os.path.join(directory, 'Release.gpg')) or gpg_key:
                metadata_files.append('Release.gpg')
            metadata_last_updated = max(os.path.getmtime(os.path.join(directory, fn)) for fn in metadata_files)
        except Exception:
            metadata_last_updated = 0
        # If the repository doesn't actually need to be updated we'll skip the update.
        if metadata_last_updated >= contents_last_updated:
            logger.info("Contents of repository %s didn't change, so no need to update it.", directory)
            return
        # The generated files `Packages', `Packages.gz', `Release' and `Release.gpg'
        # are created in a temporary directory. Only once all of the files have been
        # successfully generated they are moved to the repository directory. There
        # are two reasons for this:
        #
        # 1. If the repository directory is being served to apt-get clients we
        #    don't want them to catch us in the middle of updating the repository
        #    because it will be in an inconsistent state.
        #
        # 2. If we fail to generate one of the files it's better not to have
        #    changed any of them, for the same reason as point one :-)
        logger.info("%s trivial repository %s ..", "Updating" if metadata_last_updated else "Creating", directory)
        temporary_directory = tempfile.mkdtemp()
        try:
            # Generate the `Packages' file.
            logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Packages')))
            scan_packages(repository=directory,
                          packages_file=os.path.join(temporary_directory, 'Packages'))
            # Generate the `Packages.gz' file by compressing the `Packages' file.
            logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Packages.gz')))
            execute("gzip < Packages > Packages.gz", directory=temporary_directory, logger=logger)
            # Generate the `Release' file.
            logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Release')))
            # Get APT::FTPArchive::Release::* options from configuration file.
            release_fields = dict((k.lower(), v) for k, v in release_fields.items())
            for name, value in load_config(directory).items():
                if name.startswith('release-'):
                    name = re.sub('^release-', '', name)
                    if name not in release_fields:
                        release_fields[name] = value
            # Override APT::FTPArchive::Release::* options from configuration file
            # with options given to update_repository() explicitly by the caller.
            options = []
            for name, value in release_fields.items():
                name = 'APT::FTPArchive::Release::%s' % name.capitalize()
                options.append('-o %s' % pipes.quote('%s=%s' % (name, value)))
            command = "LANG= apt-ftparchive %s release ." % ' '.join(options)
            release_listing = execute(command, capture=True, directory=temporary_directory, logger=logger)
            with open(os.path.join(temporary_directory, 'Release'), 'w') as handle:
                handle.write(release_listing + '\n')
            # Generate the `Release.gpg' file by signing the `Release' file with GPG?
            gpg_key_file = os.path.join(directory, 'Release.gpg')
            if gpg_key:
                logger.debug("Generating file: %s", format_path(gpg_key_file))
                initialize_gnupg()
                command = "{gpg} --armor --sign --detach-sign --output Release.gpg Release"
                execute(command.format(gpg=gpg_key.gpg_command), directory=temporary_directory, logger=logger)
            elif os.path.isfile(gpg_key_file):
                # XXX If 1) no GPG key was provided, 2) apt doesn't require the
                # repository to be signed and 3) `Release.gpg' exists from a
                # previous run, this file should be removed so we don't create an
                # inconsistent repository index (when `Release' is updated but
                # `Release.gpg' is not updated the signature becomes invalid).
                os.unlink(gpg_key_file)
            # Move the generated files into the repository directory.
            for entry in os.listdir(temporary_directory):
                shutil.copy(os.path.join(temporary_directory, entry), os.path.join(directory, entry))
            logger.info("Finished updating trivial repository in %s.", timer)
        finally:
            shutil.rmtree(temporary_directory)

def activate_repository(directory, gpg_key=None):
    """
    Set everything up so that a trivial Debian package repository can be used
    to install packages without a webserver (this uses the ``file://`` URL
    scheme to point ``apt-get`` to a directory on the local file system).

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param gpg_key: The :py:class:`deb_pkg_tools.gpg.GPGKey` object used to
                    sign the repository. Defaults to the result of
                    :py:func:`select_gpg_key()`.

    .. warning:: This function requires ``root`` privileges to:

                 1. create the directory ``/etc/apt/sources.list.d``,
                 2. create a ``*.list`` file in ``/etc/apt/sources.list.d`` and
                 3. run ``apt-get update``.

                 This function will use ``sudo`` to gain ``root`` privileges
                 when it's not already running as ``root``.
    """
    directory = os.path.realpath(directory)
    logger.debug("Activating repository: %s", format_path(directory))
    # Generate the `sources.list' file.
    sources_directory = '/etc/apt/sources.list.d'
    execute('mkdir', '-p', sources_directory, sudo=True, logger=logger)
    sources_file = os.path.join(sources_directory, '%s.list' % sha1(directory))
    logger.debug("Generating file: %s", sources_file)
    sources_entry = ['deb']
    if apt_supports_trusted_option():
        sources_entry.append('[trusted=yes]')
    sources_entry.append('file://%s' % directory)
    sources_entry.append('./')
    command = "echo {text} > {file}"
    execute(command.format(text=pipes.quote(' '.join(sources_entry)),
                           file=pipes.quote(sources_file)),
            sudo=True, logger=logger)
    # Make apt-get accept the repository signing key?
    gpg_key = gpg_key or select_gpg_key(directory)
    if gpg_key:
        logger.info("Installing GPG key for automatic signing ..")
        initialize_gnupg()
        command = '{gpg} --armor --export | apt-key add -'
        execute(command.format(gpg=gpg_key.gpg_command), sudo=True, logger=logger)
    # Update the package list (make sure it works).
    logger.debug("Updating package list ..")
    execute("apt-get update", sudo=True, logger=logger)

def deactivate_repository(directory):
    """
    Deactivate a trivial Debian package repository that was previously
    activated using :py:func:`activate_repository()`.

    :param directory: The pathname of a directory with ``*.deb`` packages.

    .. warning:: This function requires ``root`` privileges to:

                 1. delete a ``*.list`` file in ``/etc/apt/sources.list.d`` and
                 2. run ``apt-get update``.

                 This function will use ``sudo`` to gain ``root`` privileges
                 when it's not already running as ``root``.
    """
    directory = os.path.realpath(directory)
    logger.debug("Deactivating repository: %s", format_path(directory))
    # Remove the `sources.list' file.
    sources_file = os.path.join('/etc/apt/sources.list.d', '%s.list' % sha1(directory))
    logger.debug("Removing file: %s", sources_file)
    execute('rm', '-f', sources_file, sudo=True, logger=logger)
    # Update the package list (cleanup).
    logger.debug("Updating package list ..")
    execute("apt-get update", sudo=True, logger=logger)

def with_repository(directory, *command):
    """
    Create/update a trivial package repository, activate the repository, run an
    external command (usually ``apt-get install``) and finally deactivate the
    repository again. Also deactivates the repository when the external command
    fails and :py:exc:`executor.ExternalCommandFailed` is raised.

    :param directory: The pathname of a directory containing ``*.deb`` archives
                      (a string).
    :param command: The command to execute (a tuple of strings, passed verbatim
                    to :py:func:`executor.execute()`).
    """
    update_repository(directory)
    activate_repository(directory)
    try:
        execute(*command, logger=logger)
    finally:
        deactivate_repository(directory)

# Use a global to cache the answer of apt_supports_trusted_option() so we don't
# execute `dpkg-query --show' and `dpkg --compare-versions' more than once.
trusted_option_supported = None

def apt_supports_trusted_option():
    """
    Since apt version 0.8.16~exp3 the option ``[trusted=yes]`` can be used in a
    ``sources.list`` file to disable GPG key checking (see `Debian bug
    #596498`_). This version of apt is included with Ubuntu 12.04 and later,
    but deb-pkg-tools also has to support older versions of apt. The
    :py:func:`apt_supports_trusted_option()` function checks if the installed
    version of apt supports the ``[trusted=yes]`` option, so that deb-pkg-tools
    can use it when possible.

    :returns: ``True`` if the option is supported, ``False`` if it is not.

    .. _Debian bug #596498: http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=596498
    """
    global trusted_option_supported
    if trusted_option_supported is None:
        try:
            # Find the installed version of the `apt' package.
            version = execute('dpkg-query','--show', '--showformat=${Version}', 'apt', capture=True)
            # Check if the version is >= 0.8.16 (which includes [trusted=yes] support).
            execute('dpkg','--compare-versions', version, 'ge', '0.8.16~exp3')
            # If ExternalCommandFailed  is not raised,
            # `dpkg --compare-versions' reported succes.
            trusted_option_supported = True
        except ExternalCommandFailed:
            trusted_option_supported = False
    return trusted_option_supported

def select_gpg_key(directory):
    """
    Select a suitable GPG key for repository signing (for use in
    :py:func:`update_repository()` and :py:func:`activate_repository()`). First
    the following locations are checked for a configuration file:

    1. ``~/.deb-pkg-tools/repos.ini``
    2. ``/etc/deb-pkg-tools/repos.ini``

    If both files exist the first one is used. Here is an example configuration
    with an explicit repository/key pair and a default key:

    .. code-block:: ini

        [default]
        public-key-file = ~/.deb-pkg-tools/default.pub
        secret-key-file = ~/.deb-pkg-tools/default.sec

        [test]
        public-key-file = ~/.deb-pkg-tools/test.pub
        secret-key-file = ~/.deb-pkg-tools/test.sec
        directory = /tmp

    Hopefully this is self explanatory: If the repository directory is ``/tmp``
    the 'test' key pair is used, otherwise the 'default' key pair is used. The
    'directory' field can contain globbing wildcards like ``?`` and ``*``. Of
    course you're free to put the actual ``*.pub`` and ``*.sec`` files anywhere
    you like; that's the point of having them be configurable :-)

    If no GPG keys are configured but apt requires local repositories to be
    signed then this function falls back to selecting an automatically
    generated signing key. The generated public key and secret key are stored
    in the directory ``~/.deb-pkg-tools``.

    :param directory: The pathname of the directory that contains the package
                      repository to sign.
    :returns: A :py:class:`deb_pkg_tools.gpg.GPGKey` object or ``None``.
    """
    # Check if the user has configured one or more GPG keys.
    options = load_config(directory)
    if 'secret-key-file' in options and 'public-key-file' in options:
        return GPGKey(secret_key_file=os.path.expanduser(options['secret-key-file']),
                      public_key_file=os.path.expanduser(options['public-key-file']))
    if apt_supports_trusted_option():
        # No GPG key was given and no GPG key was configured, however apt
        # supports the [trusted] option so we'll assume the user doesn't care
        # about signing.
        logger.debug("No GPG key specified but your version of apt doesn't require signing so I'll just skip it :-)")
    else:
        # No GPG key was given and no GPG key was configured, but apt doesn't
        # support the [trusted] option so we'll have to sign the repository
        # anyway.
        logger.debug("No GPG key specified but your version of apt doesn't support the [trusted] option, so I will have to sign the repository anyway ..")
        # XXX About the choice of `user_config_directory' here vs.
        # `system_config_directory': Since we're generating a private
        # key we shouldn't ever store it in a non-secure location.
        return GPGKey(name="deb-pkg-tools",
                      description="Automatic signing key for deb-pkg-tools",
                      secret_key_file=os.path.join(config.user_config_directory, 'automatic-signing-key.sec'),
                      public_key_file=os.path.join(config.user_config_directory, 'automatic-signing-key.pub'))

def load_config(repository):
    repository = os.path.abspath(repository)
    for config_dir in (config.user_config_directory, config.system_config_directory):
        config_file = os.path.join(config_dir, config.repo_config_file)
        if os.path.isfile(config_file):
            logger.debug("Loading configuration from %s ..", format_path(config_file))
            parser = configparser.RawConfigParser()
            parser.read(config_file)
            sections = dict((n, dict(parser.items(n))) for n in parser.sections())
            defaults = sections.get('default', {})
            logger.debug("Found %i sections: %s", len(sections), concatenate(parser.sections()))
            for name, options in sections.items():
                directory = options.get('directory')
                if directory and fnmatch.fnmatch(repository, directory):
                    defaults.update(options)
                    return defaults
    return {}

# vim: ts=4 sw=4 et
