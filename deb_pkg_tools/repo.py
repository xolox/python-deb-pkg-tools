# Debian packaging tools: Trivial repository management.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: October 21, 2013
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
from deb_pkg_tools.utils import execute, find_home_directory, sha1
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
                    sign the repository. Defaults to the automatic signing key
                    managed by deb-pkg-tools.
    """
    # Figure out when the repository contents were last updated.
    contents_last_updated = 0
    for entry in os.listdir(directory):
        if entry.endswith('.deb'):
            pathname = os.path.join(directory, entry)
            contents_last_updated = max(contents_last_updated, os.path.getmtime(pathname))
    # Figure out when the repository metadata was last updated.
    try:
        metadata_files = ['Packages', 'Packages.gz', 'Release', 'Release.gpg']
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
        # Generate the `Release.gpg' file by signing the `Release' file with GPG.
        initialize_gnupg()
        if not gpg_key:
            gpg_key = generate_automatic_signing_key()
        logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Release.gpg')))
        command = "rm -f Release.gpg && gpg -abs --no-default-keyring --secret-keyring {secret} --keyring {public} -o Release.gpg Release"
        execute(command.format(secret=pipes.quote(gpg_key.secret_key_file),
                               public=pipes.quote(gpg_key.public_key_file)),
                directory=directory, logger=logger)

def activate_repository(directory, gpg_key=None):
    """
    Set everything up so that a trivial Debian package repository can be used
    to install packages without a webserver (this uses the ``file://`` URL
    scheme to point ``apt-get`` to a directory on the local file system).

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param gpg_key: The :py:class:`deb_pkg_tools.gpg.GPGKey` object used to
                    sign the repository. Defaults to the automatic signing key
                    managed by deb-pkg-tools.
    """
    directory = os.path.realpath(directory)
    logger.debug("Activating repository: %s", format_path(directory))
    # Generate the `sources.list' file.
    sources_directory = '/etc/apt/sources.list.d'
    execute('mkdir', '-p', sources_directory, sudo=True, logger=logger)
    sources_file = os.path.join(sources_directory, '%s.list' % sha1(directory))
    sources_entry = 'deb file://%s ./' % directory
    logger.debug("Generating file: %s", sources_file)
    command = "echo {text} > {file}"
    execute(command.format(text=pipes.quote(sources_entry),
                           file=pipes.quote(sources_file)),
            sudo=True, logger=logger)
    # Make apt-get accept the automatic signing key.
    logger.info("Installing GPG key for automatic signing ..")
    initialize_gnupg()
    if not gpg_key:
        gpg_key = generate_automatic_signing_key()
    command = 'gpg --armor --export --no-default-keyring --secret-keyring {secret} --keyring {public} | apt-key add -'
    execute(command.format(secret=pipes.quote(gpg_key.secret_key_file),
                           public=pipes.quote(gpg_key.public_key_file)),
            sudo=True, logger=logger)
    # Update the package list (make sure it works).
    logger.debug("Updating package list ..")
    execute("apt-get update", sudo=True, logger=logger)

def deactivate_repository(directory):
    """
    Deactivate a trivial Debian package repository that was previously
    activated using :py:func:`activate_repository()`.

    :param directory: The pathname of a directory with ``*.deb`` packages.

    .. note:: This function assumes it is running as ``root``; it won't work
              without root access.
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

def generate_automatic_signing_key():
    """
    Generate the GPG key pair that deb-pkg-tools will use to automatically sign
    ``Release`` files in Debian package repositories. The generated public key
    and secret key are stored in the directory ``~/.deb-pkg-tools``.
    """
    directory = os.path.join(find_home_directory(), '.deb-pkg-tools')
    return GPGKey(name="deb-pkg-tools",
                  description="Automatic signing key for deb-pkg-tools",
                  secret_key_file=os.path.join(directory, 'automatic-signing-key.sec'),
                  public_key_file=os.path.join(directory, 'automatic-signing-key.pub'))

# vim: ts=4 sw=4 et
