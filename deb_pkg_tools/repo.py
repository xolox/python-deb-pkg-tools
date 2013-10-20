# Debian packaging tools: Trivial repository management.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: October 20, 2013
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
import pwd
import tempfile
import textwrap

# External dependencies.
from humanfriendly import format_path

# Modules included in our package.
from deb_pkg_tools.utils import execute, sha1

# Initialize a logger.
logger = logging.getLogger(__name__)

def update_repository(directory, release_fields={}):
    """
    Create or update a `trivial repository`_ using the Debian
    commands ``dpkg-scanpackages`` and ``apt-ftparchive`` (also uses the
    external programs ``cat``, ``gpg``, ``gzip``, ``mv``, ``rm`` and ``sed``).

    :param directory: The pathname of a directory with ``*.deb`` packages.
    :param release_fields: An optional dictionary with fields to set inside the
                           ``Release`` file.
    """
    repo_exists = os.path.isfile(os.path.join(directory, 'Release.gpg'))
    logger.info("%s trivial repository: %s", "Updating" if repo_exists else "Creating", directory)
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
    secring, pubring = prepare_automatic_signing_key()
    logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Release.gpg')))
    command = "rm -f Release.gpg && gpg -abs --no-default-keyring --secret-keyring {secring} --keyring {pubring} -o Release.gpg Release"
    execute(command.format(secring=secring, pubring=pubring),
            directory=directory, logger=logger)

def activate_repository(directory):
    """
    Set everything up so that a trivial Debian package repository can be used
    to install packages without a webserver (this uses the ``file://`` URL
    scheme to point ``apt-get`` to a directory on the local file system).

    :param directory: The pathname of a directory with ``*.deb`` packages.

    .. note:: This function assumes it is running as ``root``; it won't work
              without root access.
    """
    directory = os.path.realpath(directory)
    logger.debug("Activating repository: %s", format_path(directory))
    # Generate the `sources.list' file.
    sources_directory = '/etc/apt/sources.list.d'
    execute('mkdir', '-p', sources_directory, sudo=True, logger=logger)
    sources_file = os.path.join(sources_directory, '%s.list' % sha1(directory))
    sources_entry = 'deb file://%s ./' % directory
    logger.debug("Generating file: %s", sources_file)
    execute("echo %s > %s" % (pipes.quote(sources_entry), pipes.quote(sources_file)),
            sudo=True, logger=logger)
    # Make apt-get accept the automatic signing key.
    secring, pubring = prepare_automatic_signing_key()
    logger.info("Installing GPG key for automatic signing ..")
    command = 'gpg --armor --export --no-default-keyring --secret-keyring {secring} --keyring {pubring} | apt-key add -'
    execute(command.format(secring=secring, pubring=pubring), sudo=True, logger=logger)
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

def prepare_automatic_signing_key():
    """
    Generate a GPG key that deb-pkg-tools can use to automatically sign
    ``Release`` files. This only has to be done once.
    """
    # Make sure the directory that holds the automatic signing key exists.
    directory = os.path.join(find_home_directory(), '.deb-pkg-tools')
    if not os.path.isdir(directory):
        os.makedirs(directory)
    secring = os.path.join(directory, 'automatic-signing-key.sec')
    pubring = os.path.join(directory, 'automatic-signing-key.pub')
    # See if the automatic signing key was previously generated.
    if not (os.path.isfile(secring) and os.path.isfile(pubring)):
        # Generate batch instructions for `gpg --batch --gen-key'.
        fd, pathname = tempfile.mkstemp()
        with open(pathname, 'w') as handle:
            handle.write(textwrap.dedent('''
                %echo Generating automatic signing key for deb-pkg-tools (this can take a while, but you only need to do it once)
                Key-Type: DSA
                Key-Length: 1024
                Subkey-Type: ELG-E
                Subkey-Length: 1024
                Name-Real: deb-pkg-tools
                Name-Comment: Automatic signing key for deb-pkg-tools
                Name-Email: none
                Expire-Date: 0
                %pubring {pubring}
                %secring {secring}
                %commit
                %echo Finished generating automatic signing key for deb-pkg-tools!
            ''').format(secring=secring, pubring=pubring))
        # Generate the automatic signing key.
        logger.info("Generating GPG key for automatic signing ..")
        execute('gpg', '--batch', '--gen-key', pathname, logger=logger)
    return secring, pubring

def find_home_directory():
    """
    Determine the home directory of the current user.
    """
    try:
        home = os.path.realpath(os.environ['HOME'])
        assert os.path.isdir(home)
        return home
    except Exception:
        return pwd.getpwuid(os.getuid()).pw_dir

# vim: ts=4 sw=4 et
