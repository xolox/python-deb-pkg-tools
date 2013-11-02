# Debian packaging tools: Trivial repository management.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 2, 2013
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

All of the functions in this module can raise
:py:exc:`deb_pkg_tools.utils.ExternalCommandFailed`.

.. _trivial repository: http://www.debian.org/doc/manuals/repository-howto/repository-howto#id443677
"""

# Standard library modules.
import logging
import os.path
import pipes

# External dependencies.
from humanfriendly import format_path

# Modules included in our package.
from deb_pkg_tools.utils import (execute, find_home_directory, sha1,
                                 ExternalCommandFailed)
from deb_pkg_tools.gpg import GPGKey, initialize_gnupg

# Initialize a logger.
logger = logging.getLogger(__name__)

def update_repository(directory, release_fields={}, gpg_key=None):
    """
    Create or update a `trivial repository`_ using the Debian
    commands ``dpkg-scanpackages`` and ``apt-ftparchive`` (also uses the
    external programs ``cat``, ``gpg``, ``gzip``, ``mv``, ``rm`` and ``sed``).

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param release_fields: An optional dictionary with fields to set inside the
                           ``Release`` file.
    :param gpg_key: The :py:class:`deb_pkg_tools.gpg.GPGKey` object used to
                    sign the repository. Defaults to the result of
                    :py:func:`fallback_to_generated_gpg_key()`.
    """
    gpg_key = fallback_to_generated_gpg_key(gpg_key)
    # Figure out when the repository contents were last updated.
    contents_last_updated = 0
    for entry in os.listdir(directory):
        if entry.endswith('.deb'):
            pathname = os.path.join(directory, entry)
            contents_last_updated = max(contents_last_updated, os.path.getmtime(pathname))
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
    else:
        logger.info("%s trivial repository: %s", "Updating" if metadata_last_updated else "Creating", directory)
        # Generate the `Packages' file.
        logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Packages')))
        execute("dpkg-scanpackages -m . > Packages", directory=directory, logger=logger)
        # Fix the syntax of the `Packages' file using sed.
        execute('sed', '-i', 's@: \./@: @', 'Packages', directory=directory, logger=logger)
        # Generate the `Packages.gz' file by compressing the `Packages' file.
        logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Packages.gz')))
        execute("gzip < Packages > Packages.gz", directory=directory, logger=logger)
        # Generate the `Release' file.
        logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Release')))
        options = []
        for name, value in release_fields.iteritems():
            name = 'APT::FTPArchive::Release::%s' % name.capitalize()
            options.append('-o %s' % pipes.quote('%s=%s' % (name, value)))
        command = "rm -f Release && LANG= apt-ftparchive {options} release . > Release.tmp && mv Release.tmp Release"
        execute(command.format(options=' '.join(options)), directory=directory, logger=logger)
        # Generate the `Release.gpg' file by signing the `Release' file with GPG?
        filename = os.path.join(directory, 'Release.gpg')
        if os.path.isfile(filename):
            # XXX If 1) no GPG key was provided, 2) apt doesn't require the
            # repository to be signed and 3) `Release.gpg' exists from a
            # previous run, this file should be removed so we don't create an
            # inconsistent repository index (when `Release' is updated but
            # `Release.gpg' is not updated the signature becomes invalid).
            execute("rm -f Release.gpg", directory=directory, logger=logger)
        if gpg_key:
            logger.debug("Generating file: %s", format_path(filename))
            initialize_gnupg()
            command = "{gpg} --armor --sign --detach-sign --output Release.gpg Release"
            execute(command.format(gpg=gpg_key.gpg_command), directory=directory, logger=logger)

def activate_repository(directory, gpg_key=None):
    """
    Set everything up so that a trivial Debian package repository can be used
    to install packages without a webserver (this uses the ``file://`` URL
    scheme to point ``apt-get`` to a directory on the local file system).

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param gpg_key: The :py:class:`deb_pkg_tools.gpg.GPGKey` object used to
                    sign the repository. Defaults to the result of
                    :py:func:`fallback_to_generated_gpg_key()`.

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
    gpg_key = fallback_to_generated_gpg_key(gpg_key)
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

def fallback_to_generated_gpg_key(gpg_key):
    """
    Select the automatically generated signing key only when no GPG key was
    provided by the user yet apt requires the repository to be signed. The
    generated public key and secret key are stored in the directory
    ``~/.deb-pkg-tools``.

    :param gpg_key: The :py:class:`deb_pkg_tools.gpg.GPGKey` object provided by
                    the caller (if any).
    :returns: A :py:class:`deb_pkg_tools.gpg.GPGKey` object. If the caller
              provided a GPG key that will be returned. If the caller did not
              provide a GPG key but apt requires the repository to be signed,
              the automatic signing key managed by deb-pkg-tools is returned.
              Otherwise ``None`` is returned.
    """
    if not gpg_key:
        if apt_supports_trusted_option():
            logger.debug("No GPG key specified but your version of apt doesn't require signing so I'll just skip it :-)")
        else:
            logger.debug("No GPG key specified but your version of apt doesn't support the [trusted] option, so I will have to sign the repository anyway ..")
            directory = os.path.join(find_home_directory(), '.deb-pkg-tools')
            gpg_key = GPGKey(name="deb-pkg-tools",
                             description="Automatic signing key for deb-pkg-tools",
                             secret_key_file=os.path.join(directory, 'automatic-signing-key.sec'),
                             public_key_file=os.path.join(directory, 'automatic-signing-key.pub'))
    return gpg_key

# vim: ts=4 sw=4 et
