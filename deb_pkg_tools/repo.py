# Debian packaging tools: Trivial repository management.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: August 4, 2013
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
from deb_pkg_tools.utils import execute, sha1, ExternalCommandFailed

# Initialize a logger.
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def update_repository(directory):
    """
    Create or update a `trivial repository`_ using the Debian
    commands ``dpkg-scanpackages`` and ``apt-ftparchive`` (also uses the
    external programs ``cat``, ``gpg``, ``gzip``, ``mv``, ``rm`` and ``sed``).

    Raises :py:exc:`FailedToSignRelease` when GPG fails to sign the ``Release``
    file (most likely because the current user doesn't have a private GPG key;
    you can generate one using ``gpg --gen-key``, as explained in the error
    message).

    :param directory: The pathname of a directory with ``*.deb`` packages.
    """
    repo_exists = os.path.isfile(os.path.join(directory, 'Release.gpg'))
    logger.info("%s trivial repository: %s", "Updating" if repo_exists else "Creating", directory)
    # Generate the `Packages' file.
    logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Packages')))
    execute("dpkg-scanpackages -m . > Packages", directory)
    # Fix the syntax of the `Packages' file using sed.
    execute("sed -i 's@: \./@: @' Packages", directory)
    # Generate the `Packages.gz' file by compressing the `Packages' file.
    logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Packages.gz')))
    execute("gzip < Packages > Packages.gz", directory)
    # Generate the `Release' file.
    logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Release')))
    execute("rm -f Release && LANG= apt-ftparchive release . > Release.tmp && mv Release.tmp Release", directory)
    # Generate the `Release.gpg' file by signing the `Release' file with GPG.
    logger.debug("Generating file: %s", format_path(os.path.join(directory, 'Release.gpg')))
    try:
        execute("rm -f Release.gpg && gpg -abs -o Release.gpg Release", directory)
    except ExternalCommandFailed, e:
        msg = "Failed to sign `Release' file! Most likely you don't have a private GPG key. In that case, please create a private GPG key using 'gpg --gen-key'. Original exception: %s"
        raise FailedToSignRelease, msg % unicode(e)

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
    logger.debug("Activating repository: %s", directory)
    # Generate the `sources.list' file.
    sources_directory = '/etc/apt/sources.list.d'
    execute("mkdir -p %s" % pipes.quote(sources_directory))
    sources_file = os.path.join(sources_directory, '%s.list' % sha1(directory))
    sources_entry = 'deb file://%s ./' % directory
    logger.debug("Generating file: %s", sources_file)
    execute("echo %s > %s" % (pipes.quote(sources_entry), pipes.quote(sources_file)))
    # Make the GPG key pair known to `apt-get'.
    logger.debug("Installing GPG key ..")
    execute("gpg --armor --export | apt-key add -")
    # Update the package list (make sure it works).
    logger.debug("Updating package list ..")
    execute("apt-get update")

def deactivate_repository(directory):
    """
    Deactivate a trivial Debian package repository that was previously
    activated using :py:func:`activate_repository()`.

    :param directory: The pathname of a directory with ``*.deb`` packages.

    .. note:: This function assumes it is running as ``root``; it won't work
              without root access.
    """
    directory = os.path.realpath(directory)
    logger.debug("Deactivating repository: %s", directory)
    # Remove the `sources.list' file.
    sources_file = os.path.join('/etc/apt/sources.list.d', '%s.list' % sha1(directory))
    logger.debug("Removing file: %s", sources_file)
    execute("rm -f %s" % pipes.quote(sources_file))
    # Update the package list (make sure it works).
    logger.debug("Updating package list ..")
    execute("apt-get update")

class FailedToSignRelease(Exception):
    """
    Raised by :py:func:`update_repository()` when the signing of the
    ``Release`` file fails.
    """

# vim: ts=4 sw=4 et
