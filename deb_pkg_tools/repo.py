# Debian packaging tools: Trivial repository management.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: April 10, 2015
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
import glob
import hashlib
import logging
import os
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
from humanfriendly import coerce_boolean, concatenate, format_path, Spinner, Timer

# Modules included in our package.
from deb_pkg_tools import config
from deb_pkg_tools.control import unparse_control_fields
from deb_pkg_tools.gpg import GPGKey, initialize_gnupg
from deb_pkg_tools.package import find_package_archives, inspect_package_fields
from deb_pkg_tools.utils import atomic_lock, find_installed_version, optimize_order, sha1
from deb_pkg_tools.version import Version

# Enable power users to disable the use of `sudo' (because it
# may not be available in non-Debian build environments).
ALLOW_SUDO = coerce_boolean(os.environ.get('DPT_SUDO', 'true'))

# Initialize a logger.
logger = logging.getLogger(__name__)

def scan_packages(repository, packages_file=None, cache=None):
    """
    A reimplementation of the ``dpkg-scanpackages -m`` command in Python.

    Updates a ``Packages`` file based on the Debian package archive(s) found in
    the given directory. Uses :py:class:`.PackageCache` to (optionally) speed
    up the process significantly by caching package metadata and hashes on
    disk. This explains why this function can be much faster than
    ``dpkg-scanpackages -m``.

    :param repository: The pathname of a directory containing Debian
                       package archives (a string).
    :param packages_file: The pathname of the ``Packages`` file to update
                          (a string). Defaults to the ``Packages`` file in
                          the given directory.
    :param cache: The :py:class:`.PackageCache` to use (defaults to ``None``).
    """
    # By default the `Packages' file inside the repository is updated.
    if not packages_file:
        packages_file = os.path.join(repository, 'Packages')
    # Update the `Packages' file.
    timer = Timer()
    package_archives = glob.glob(os.path.join(repository, '*.deb'))
    num_packages = len(package_archives)
    spinner = Spinner(total=num_packages)
    with open(packages_file, 'wb') as handle:
        for i, archive in enumerate(optimize_order(package_archives), start=1):
            fields = dict(inspect_package_fields(archive, cache=cache))
            fields.update(get_packages_entry(archive, cache=cache))
            deb822_dict = unparse_control_fields(fields)
            deb822_dict.dump(handle)
            handle.write(b'\n')
            spinner.step(label="Scanning package metadata", progress=i)
    spinner.clear()
    logger.debug("Wrote %i entries to output Packages file in %s.", num_packages, timer)

def get_packages_entry(pathname, cache=None):
    """
    Get a dictionary with the control fields required in a ``Packages`` file.

    :param pathname: The pathname of the package archive (a string).
    :param cache: The :py:class:`.PackageCache` to use (defaults to ``None``).
    :returns: A dictionary with control fields (see below).

    Used by :py:func:`.scan_packages()` to generate ``Packages`` files. The
    format of ``Packages`` files (part of the Debian binary package repository
    format) is fairly simple:

    - All of the fields extracted from a package archive's control file using
      :py:func:`.inspect_package_fields()` are listed (you have to get these
      fields yourself and combine the dictionaries returned by
      :py:func:`.inspect_package_fields()` and
      :py:func:`.get_packages_entry()`);

    - The field ``Filename`` contains the filename of the package archive
      relative to the ``Packages`` file (which is in the same directory in our
      case, because :py:func:`update_repository()` generates trivial
      repositories);

    - The field ``Size`` contains the size of the package archive in bytes;

    - The following fields contain package archive checksums:

      ``MD5sum``
        Calculated using :py:func:`hashlib.md5()`.

      ``SHA1``
        Calculated using :py:func:`hashlib.sha1()`.

      ``SHA256``
        Calculated using :py:func:`hashlib.sha256()`.

    The three checksums are calculated simultaneously by reading the package
    archive once, in blocks of a kilobyte. This is probably why this function
    seems to be faster than ``dpkg-scanpackages -m`` (even when used without
    caching).
    """
    if cache:
        return cache[pathname].package_fields
    # Prepare to calculate the MD5, SHA1 and SHA256 hashes.
    md5_state = hashlib.md5()
    sha1_state = hashlib.sha1()
    sha256_state = hashlib.sha256()
    # Read the file once, in blocks, calculating all hashes at once.
    with open(pathname, 'rb') as handle:
        for chunk in iter(functools.partial(handle.read, 1024), b''):
            md5_state.update(chunk)
            sha1_state.update(chunk)
            sha256_state.update(chunk)
    # Convert the hashes to hexadecimal strings and return the required fields
    # in a dictionary.
    return dict(Filename=os.path.basename(pathname),
                Size=str(os.path.getsize(pathname)),
                MD5sum=md5_state.hexdigest(),
                SHA1=sha1_state.hexdigest(),
                SHA256=sha256_state.hexdigest())

def update_repository(directory, release_fields={}, gpg_key=None, cache=None):
    """
    Create or update a `trivial repository`_ using the Debian commands
    ``dpkg-scanpackages`` (reimplemented as :py:class:`scan_packages()`) and
    ``apt-ftparchive`` (also uses the external programs ``gpg`` and ``gzip``).
    Raises :py:exc:`.ResourceLockedException` when the given repository
    directory is being updated by another process.

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param release_fields: An optional dictionary with fields to set inside the
                           ``Release`` file.
    :param gpg_key: The :py:class:`.GPGKey` object used to sign the repository.
                    Defaults to the result of :py:func:`select_gpg_key()`.
    :param cache: The :py:class:`.PackageCache` to use (defaults to ``None``).
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
                          packages_file=os.path.join(temporary_directory, 'Packages'),
                          cache=cache)
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
    :param gpg_key: The :py:class:`.GPGKey` object used to sign the repository.
                    Defaults to the result of :py:func:`select_gpg_key()`.

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
    execute('mkdir', '-p', sources_directory, sudo=ALLOW_SUDO, logger=logger)
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
            sudo=ALLOW_SUDO, logger=logger)
    # Make apt-get accept the repository signing key?
    gpg_key = gpg_key or select_gpg_key(directory)
    if gpg_key:
        logger.info("Installing GPG key for automatic signing ..")
        initialize_gnupg()
        command = '{gpg} --armor --export | apt-key add -'
        execute(command.format(gpg=gpg_key.gpg_command), sudo=ALLOW_SUDO, logger=logger)
    # Update the package list (make sure it works).
    logger.debug("Updating package list ..")
    execute("apt-get update", sudo=ALLOW_SUDO, logger=logger)

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
    execute('rm', '-f', sources_file, sudo=ALLOW_SUDO, logger=logger)
    # Update the package list (cleanup).
    logger.debug("Updating package list ..")
    execute("apt-get update", sudo=ALLOW_SUDO, logger=logger)

def with_repository(directory, *command, **kw):
    """
    Create/update a trivial package repository, activate the repository, run an
    external command (usually ``apt-get install``) and finally deactivate the
    repository again. Also deactivates the repository when the external command
    fails and :py:exc:`executor.ExternalCommandFailed` is raised.

    :param directory: The pathname of a directory containing ``*.deb`` archives
                      (a string).
    :param command: The command to execute (a tuple of strings, passed verbatim
                    to :py:func:`executor.execute()`).
    :param cache: The :py:class:`.PackageCache` to use (defaults to ``None``).
    """
    update_repository(directory=directory,
                      cache=kw.get('cache'))
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
            apt_version = Version(find_installed_version('apt'))
            # Check if the version is >= 0.8.16 (which includes [trusted=yes] support).
            trusted_option_supported = (apt_version >= Version('0.8.16~exp3'))
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
    :returns: A :py:class:`.GPGKey` object or ``None``.
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
