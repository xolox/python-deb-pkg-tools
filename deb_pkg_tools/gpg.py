# Debian packaging tools: GPG key pair generation.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: October 20, 2013
# URL: https://github.com/xolox/python-deb-pkg-tools

# Standard library modules.
import logging
import os.path
import tempfile
import textwrap
import time

# External dependencies.
from humanfriendly import format_path, format_timespan

# Modules included in our package.
from deb_pkg_tools.utils import execute

# Initialize a logger.
logger = logging.getLogger(__name__)

def generate_gpg_key(name, description, secring, pubring):
    """
    Generate a GPG key pair that can be used to automatically sign ``Release``
    files in Debian package repositories.
    """
    # Generate a file with batch instructions for `gpg --batch --gen-key'.
    fd, pathname = tempfile.mkstemp()
    with open(pathname, 'w') as handle:
        handle.write(textwrap.dedent('''
            Key-Type: DSA
            Key-Length: 1024
            Subkey-Type: ELG-E
            Subkey-Length: 1024
            Name-Real: {name}
            Name-Comment: {description}
            Name-Email: none
            Expire-Date: 0
            %pubring {pubring}
            %secring {secring}
            %commit
        ''').format(name=name, description=description,
                    secring=secring, pubring=pubring))
    # Generate the GPG key pair.
    logger.info("Generating GPG key pair %s (%s) ..", name, description)
    logger.debug("Private key: %s", format_path(secring))
    logger.debug("Public key: %s", format_path(pubring))
    logger.info("Please note: Generating a GPG key pair can take a long time. "
                "If you are logged into a virtual machine or a remote server "
                "over SSH, now is a good time to familiarize yourself with "
                "the concept of entropy and how to make more of it :-)")
    start_time = time.time()
    execute('gpg', '--batch', '--gen-key', pathname, logger=logger)
    logger.info("Finished generating GPG key pair in %s.",
                format_timespan(time.time() - start_time))
    os.unlink(pathname)
