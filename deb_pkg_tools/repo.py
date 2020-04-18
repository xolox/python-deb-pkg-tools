# Debian packaging tools: Trivial repository management.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: April 18, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Create, update and activate trivial Debian package repositories.

The functions in the :mod:`deb_pkg_tools.repo` module make it possible to
transform a directory of ``*.deb`` archives into a (temporary) Debian package
repository:

- :func:`update_repository()` creates/updates a `trivial repository`_

- :func:`activate_repository()` enables ``apt-get`` to install packages from
  the trivial repository

- :func:`deactivate_repository()` cleans up after
  :func:`activate_repository()`

All of the functions in this module can raise :exc:`executor.ExternalCommandFailed`.

You can configure the GPG key(s) used by this module through a configuration
file, please refer to the documentation of :func:`select_gpg_key()`.

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

# External dependencies.
from executor import execute, ExternalCommandFailed
from humanfriendly import coerce_boolean, format_path, Timer
from humanfriendly.decorators import cached
from humanfriendly.text import concatenate
from humanfriendly.terminal.spinners import Spinner
from six.moves import configparser

# Modules included in our package.
from deb_pkg_tools import config
from deb_pkg_tools.control import unparse_control_fields
from deb_pkg_tools.gpg import GPGKey, initialize_gnupg
from deb_pkg_tools.package import find_package_archives, inspect_package_fields
from deb_pkg_tools.utils import atomic_lock, find_installed_version, optimize_order, sha1
from deb_pkg_tools.version import Version

# Public identifiers that require documentation.
__all__ = (
    "ALLOW_SUDO",
    "activate_repository",
    "apt_supports_trusted_option",
    "deactivate_repository",
    "get_packages_entry",
    "load_config",
    "logger",
    "scan_packages",
    "select_gpg_key",
    "update_repository",
    "with_repository",
)

ALLOW_SUDO = coerce_boolean(os.environ.get('DPT_SUDO', 'true'))
"""
:data:`True` to enable the use of :man:`sudo` during operations that normally
require elevated privileges (the default), :data:`False` to disable the use of
:man:`sudo`. This option is provided for power users to disable the use of
:man:`sudo` because it may not be available in all build environments. The
environment variable ``$DPT_SUDO`` can be used to control the value of this
variable (see :func:`~humanfriendly.coerce_boolean()` for acceptable values).
"""

# Initialize a logger.
logger = logging.getLogger(__name__)


def scan_packages(repository, packages_file=None, cache=None):
    """
    A reimplementation of the ``dpkg-scanpackages -m`` command in Python.

    Updates a ``Packages`` file based on the Debian package archive(s) found in
    the given directory. Uses :class:`.PackageCache` to (optionally) speed
    up the process significantly by caching package metadata and hashes on
    disk. This explains why this function can be much faster than the
    :man:`dpkg-scanpackages` program.

    :param repository: The pathname of a directory containing Debian
                       package archives (a string).
    :param packages_file: The pathname of the ``Packages`` file to update
                          (a string). Defaults to the ``Packages`` file in
                          the given directory.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
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
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :returns: A dictionary with control fields (see below).

    Used by :func:`.scan_packages()` to generate ``Packages`` files. The
    format of ``Packages`` files (part of the Debian binary package repository
    format) is fairly simple:

    - All of the fields extracted from a package archive's control file using
      :func:`.inspect_package_fields()` are listed (you have to get these
      fields yourself and combine the dictionaries returned by
      :func:`.inspect_package_fields()` and
      :func:`.get_packages_entry()`);

    - The field ``Filename`` contains the filename of the package archive
      relative to the ``Packages`` file (which is in the same directory in our
      case, because :func:`update_repository()` generates trivial
      repositories);

    - The field ``Size`` contains the size of the package archive in bytes;

    - The following fields contain package archive checksums:

      ``MD5sum``
        Calculated using the ``md5()`` constructor of the :mod:`hashlib` module.

      ``SHA1``
        Calculated using the ``sha1()`` constructor of the :mod:`hashlib` module.

      ``SHA256``
        Calculated using the ``sha256()`` constructor of the :mod:`hashlib` module.

    The three checksums are calculated simultaneously by reading the package
    archive once, in blocks of a kilobyte. This is probably why this function
    seems to be faster than ``dpkg-scanpackages -m`` (even when used without
    caching).
    """
    if cache:
        entry = cache.get_entry('package-fields', pathname)
        value = entry.get_value()
        if value is not None:
            return value
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
    fields = dict(Filename=os.path.basename(pathname),
                  Size=str(os.path.getsize(pathname)),
                  MD5sum=md5_state.hexdigest(),
                  SHA1=sha1_state.hexdigest(),
                  SHA256=sha256_state.hexdigest())
    if cache:
        entry.set_value(fields)
    return fields


def update_repository(directory, release_fields={}, gpg_key=None, cache=None):
    """
    Create or update a `trivial repository`_.

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param release_fields: An optional dictionary with fields to set inside the
                           ``Release`` file.
    :param gpg_key: The :class:`.GPGKey` object used to sign the repository.
                    Defaults to the result of :func:`select_gpg_key()`.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :raises: :exc:`.ResourceLockedException` when the given repository
             directory is being updated by another process.

    This function is based on the Debian programs dpkg-scanpackages_ and
    apt-ftparchive_ and also uses gpg_ and gzip_. The following files are
    generated:

    ===============  ==========================================================
    Filename         Description
    ===============  ==========================================================
    ``Packages``     Provides the metadata of all ``*.deb`` packages in the
                     `trivial repository`_ as a single text file. Generated
                     using :class:`scan_packages()` (as a faster alternative
                     to dpkg-scanpackages_).
    ``Packages.gz``  A compressed version of the package metadata generated
                     using gzip_.
    ``Release``      Metadata about the release and hashes of the ``Packages``
                     and ``Packages.gz`` files. Generated using
                     apt-ftparchive_.
    ``Release.gpg``  An ASCII-armored detached GPG signature of the ``Release``
                     file. Generated using ``gpg --armor --sign
                     --detach-sign``.
    ``InRelease``    The contents of the ``Release`` file and its GPG signature
                     combined into a single human readable file. Generated
                     using ``gpg --armor --sign --clearsign``.
    ===============  ==========================================================

    For more details about the ``Release.gpg`` and ``InRelease`` files please
    refer to the Debian wiki's section on secure-apt_.

    .. _apt-ftparchive: https://manpages.debian.org/apt-ftparchive
    .. _dpkg-scanpackages: https://manpages.debian.org/dpkg-scanpackages
    .. _gpg: https://manpages.debian.org/gpg
    .. _gzip: https://manpages.debian.org/gzip
    .. _secure-apt: https://wiki.debian.org/SecureApt
    """
    with atomic_lock(directory):
        timer = Timer()
        gpg_key = gpg_key or select_gpg_key(directory)
        # Figure out when the repository contents were last updated.
        contents_last_updated = os.path.getmtime(directory)
        for archive in find_package_archives(directory, cache=cache):
            contents_last_updated = max(contents_last_updated, os.path.getmtime(archive.filename))
        # Figure out when the repository metadata was last updated.
        try:
            metadata_files = ['Packages', 'Packages.gz', 'Release']
            # XXX If 1) no GPG key was provided, 2) apt doesn't require the
            # repository to be signed and 3) `Release.gpg' doesn't exist, it should
            # not cause an unnecessary repository update. That would turn the
            # conditional update into an unconditional update, which is not the
            # intention here :-)
            for signed_file in 'Release.gpg', 'InRelease':
                if os.path.isfile(os.path.join(directory, signed_file)) or gpg_key:
                    metadata_files.append(signed_file)
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
        temporary_directory = tempfile.mkdtemp(prefix='deb-pkg-tools-', suffix='-update-repo-stage')
        logger.debug("Using temporary directory: %s", temporary_directory)
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
            # Generate the `Release.gpg' and `InRelease' files by signing the `Release' file with GPG?
            gpg_key_file = os.path.join(directory, 'Release.gpg')
            in_release_file = os.path.join(directory, 'InRelease')
            if gpg_key:
                initialize_gnupg()
                logger.debug("Generating file: %s", format_path(gpg_key_file))
                command = "{gpg} --armor --sign --detach-sign --output Release.gpg Release"
                execute(command.format(gpg=gpg_key.gpg_command), directory=temporary_directory, logger=logger)
                logger.debug("Generating file: %s", format_path(in_release_file))
                command = "{gpg} --armor --sign --clearsign --output InRelease Release"
                execute(command.format(gpg=gpg_key.gpg_command), directory=temporary_directory, logger=logger)
            else:
                # XXX If 1) no GPG key was provided, 2) apt doesn't require the
                # repository to be signed and 3) `Release.gpg' exists from a
                # previous run, this file should be removed so we don't create an
                # inconsistent repository index (when `Release' is updated but
                # `Release.gpg' is not updated the signature becomes invalid).
                for stale_file in gpg_key_file, in_release_file:
                    if os.path.isfile(stale_file):
                        os.unlink(stale_file)
            # Move the generated files into the repository directory.
            for entry in os.listdir(temporary_directory):
                shutil.copy(os.path.join(temporary_directory, entry), os.path.join(directory, entry))
            logger.info("Finished updating trivial repository in %s.", timer)
        finally:
            shutil.rmtree(temporary_directory)


def activate_repository(directory, gpg_key=None):
    """
    Activate a local trivial repository.

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param gpg_key: The :class:`.GPGKey` object used to sign the repository.
                    Defaults to the result of :func:`select_gpg_key()`.

    This function sets everything up so that a trivial Debian package
    repository can be used to install packages without a webserver. This uses
    the ``file://`` URL scheme to point :man:`apt-get` to a directory on the
    local file system.

    .. warning:: This function requires ``root`` privileges to:

                 1. create the directory ``/etc/apt/sources.list.d``,
                 2. create a ``*.list`` file in ``/etc/apt/sources.list.d`` and
                 3. run ``apt-get update``.

                 This function will use :man:`sudo` to gain ``root`` privileges
                 when it's not already running as ``root``.

    .. seealso:: :data:`ALLOW_SUDO`
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
    Deactivate a local repository that was previously activated using :func:`activate_repository()`.

    :param directory: The pathname of a directory with ``*.deb`` packages.

    .. warning:: This function requires ``root`` privileges to:

                 1. delete a ``*.list`` file in ``/etc/apt/sources.list.d`` and
                 2. run ``apt-get update``.

                 This function will use :man:`sudo` to gain ``root`` privileges
                 when it's not already running as ``root``.

    .. seealso:: :data:`ALLOW_SUDO`
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
    Execute an external command while a repository is activated.

    :param directory: The pathname of a directory containing ``*.deb`` archives
                      (a string).
    :param command: The command to execute (a tuple of strings, passed verbatim
                    to :func:`executor.execute()`).
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :raises: :exc:`executor.ExternalCommandFailed` if any external commands fail.

    This function create or updates a trivial package repository, activates the
    repository, runs an external command (usually ``apt-get install``) and
    finally deactivates the repository again. Also deactivates the repository
    when the external command fails and :exc:`executor.ExternalCommandFailed`
    is raised.

    .. seealso:: :data:`ALLOW_SUDO`
    """
    update_repository(directory=directory,
                      cache=kw.get('cache'))
    activate_repository(directory)
    try:
        execute(*command, logger=logger)
    finally:
        deactivate_repository(directory)


@cached
def apt_supports_trusted_option():
    """
    Figure out whether apt supports the ``[trusted=yes]`` option.

    :returns: :data:`True` if the option is supported, :data:`False` if it is not.

    Since apt version 0.8.16~exp3 the option ``[trusted=yes]`` can be used in a
    ``sources.list`` file to disable GPG key checking (see `Debian bug
    #596498`_). This version of apt is included with Ubuntu 12.04 and later,
    but deb-pkg-tools also has to support older versions of apt. The
    :func:`apt_supports_trusted_option()` function checks if the installed
    version of apt supports the ``[trusted=yes]`` option, so that deb-pkg-tools
    can use it when possible.

    .. _Debian bug #596498: http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=596498
    """
    try:
        # Find the installed version of the `apt' package.
        apt_version = Version(find_installed_version('apt'))
        # Check if the version is >= 0.8.16 (which includes [trusted=yes] support).
        return (apt_version >= Version('0.8.16~exp3'))
    except ExternalCommandFailed:
        return False


def select_gpg_key(directory):
    """
    Select a suitable GPG key for repository signing.

    :param directory: The pathname of the directory that contains the package
                      repository to sign (a string).
    :returns: A :class:`.GPGKey` object or :data:`None`.

    Used by :func:`update_repository()` and :func:`activate_repository()` to
    select the GPG key for repository signing based on a configuration file.

    **Configuration file locations:**

    The following locations are checked for a configuration file:

    1. ``~/.deb-pkg-tools/repos.ini``
    2. ``/etc/deb-pkg-tools/repos.ini``

    If both files exist only the first one is used.

    **Configuration file contents:**

    The configuration files are in the ``*.ini`` file format (refer to the
    :mod:`ConfigParser` module for details). Each section in the configuration
    file defines a signing key.

    The ``directory`` option controls to which directory or directories a
    signing key applies. The value of this option is the pathname of a
    directory and supports pattern matching using ``?`` and ``*`` (see the
    :mod:`fnmatch` module for details).

    **The default signing key:**

    If a section does not define a ``directory`` option then that section is
    used as the default signing key for directories that are not otherwise
    matched (by a ``directory`` option).

    **Compatibility with GnuPG >= 2.1:**

    `GnuPG 2.1 compatibility`_ was implemented in deb-pkg-tools release 5.0
    which changes how users are expected to select an isolated GPG key pair:

    - Before deb-pkg-tools 5.0 only GnuPG < 2.1 was supported and the
      configuration used the ``public-key-file`` and ``secret-key-file``
      options to configure the pathnames of the public key file and
      the secret key file:

      .. code-block:: ini

         [old-example]
         public-key-file = ~/.deb-pkg-tools/default-signing-key.pub
         secret-key-file = ~/.deb-pkg-tools/default-signing-key.sec

    - In deb-pkg-tools 5.0 support for GnuPG >= 2.1 was added which means the
      public key and secret key files are no longer configured separately,
      instead a ``key-store`` option is used to point to a directory in the
      format of ``~/.gnupg`` containing the key pair:

      .. code-block:: ini

         [new-example]
         key-store = ~/.deb-pkg-tools/default-signing-key/

      Additionally a ``key-id`` option was added to make it possible to select
      a specific key pair from a GnuPG profile directory.

    **Staying backwards compatible:**

    By specifying all three of the ``public-key-file``, ``secret-key-file`` and
    ``key-store`` options it is possible to achieve compatibility with all
    supported GnuPG versions:

    - When GnuPG >= 2.1 is installed the ``key-store`` option will be used.

    - When GnuPG < 2.1 is installed the ``public-key-file`` and
      ``secret-key-file`` options will be used.

    In this case the caller is responsible for making sure that a suitable key
    pair is available in both locations (compatible with the appropriate
    version of GnuPG).

    **Default behavior:**

    If no GPG keys are configured but apt requires local repositories to be
    signed (see :func:`apt_supports_trusted_option()`) then this function falls
    back to selecting an automatically generated signing key. The generated key
    pair is stored in the directory ``~/.deb-pkg-tools``.
    """
    # Check if the user has configured one or more GPG keys.
    options = load_config(directory)
    mapping = [
        ('key-id', 'key_id'),
        ('key-store', 'directory'),
        ('public-key-file', 'public_key_file'),
        ('secret-key-file', 'secret_key_file'),
    ]
    mapped_options = dict(
        (property_name, options[option_name])
        for option_name, property_name in mapping
        if options.get(option_name)
    )
    if mapped_options:
        return GPGKey(**mapped_options)
    if apt_supports_trusted_option():
        # No GPG key was given and no GPG key was configured, however apt
        # supports the [trusted] option so we'll assume the user doesn't care
        # about signing.
        logger.debug("No GPG key specified but your version of apt"
                     " doesn't require signing so I'll just skip it :-)")
    else:
        # No GPG key was given and no GPG key was configured, but apt doesn't
        # support the [trusted] option so we'll have to sign the repository
        # anyway.
        logger.debug("No GPG key specified but your version of apt"
                     " doesn't support the [trusted] option, so I"
                     " will have to sign the repository anyway ..")
        # XXX About the choice of `user_config_directory' here vs.
        # `system_config_directory': Since we're generating a private
        # key we shouldn't ever store it in a non-secure location.
        return GPGKey(
            # These options are required in order to generate a key pair.
            name="deb-pkg-tools",
            description="Automatic signing key for deb-pkg-tools",
            # These options are required for compatibility with GnuPG < 2.1.
            public_key_file=os.path.join(config.user_config_directory, 'automatic-signing-key.pub'),
            secret_key_file=os.path.join(config.user_config_directory, 'automatic-signing-key.sec'),
            # This option is required for compatibility with GnuPG >= 2.1.
            directory=os.path.join(config.user_config_directory, 'automatic-signing-key'),
        )


def load_config(repository):
    """Load repository configuration from a ``repos.ini`` file."""
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
