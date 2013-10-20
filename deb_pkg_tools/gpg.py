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

class GPGKey(object):

    """
    Container for GPG key pairs that can be used to automatically sign
    ``Release`` files in Debian package repositories. If the given GPG key pair
    doesn't exist yet it will be automatically created without user interaction
    (except gathering of entropy, which is not something I can automate :-).
    """

    def __init__(self, name, description, secret_key_file, public_key_file):
        self.name = name
        self.description = description
        self.secret_key_file = secret_key_file
        self.public_key_file = public_key_file
        if not (os.path.isfile(secret_key_file) and os.path.isfile(public_key_file)):
            # Make sure the directory that holds the automatic signing key exists.
            for filename in [secret_key_file, public_key_file]:
                directory = os.path.dirname(filename)
                if not os.path.isdir(directory):
                    os.makedirs(directory)
            # Generate a file with batch instructions
            # suitable for `gpg --batch --gen-key'.
            fd, gpg_script = tempfile.mkstemp()
            with open(gpg_script, 'w') as handle:
                handle.write(textwrap.dedent('''
                    Key-Type: DSA
                    Key-Length: 1024
                    Subkey-Type: ELG-E
                    Subkey-Length: 1024
                    Name-Real: {name}
                    Name-Comment: {description}
                    Name-Email: none
                    Expire-Date: 0
                    %pubring {public_key_file}
                    %secring {secret_key_file}
                    %commit
                ''').format(name=self.name,
                            description=self.description,
                            secret_key_file=self.secret_key_file,
                            public_key_file=self.public_key_file))
            # Generate the GPG key pair.
            logger.info("Generating GPG key pair %s (%s) ..", self.name, self.description)
            logger.debug("Private key: %s", format_path(self.secret_key_file))
            logger.debug("Public key: %s", format_path(self.public_key_file))
            logger.info("Please note: Generating a GPG key pair can take a long time. "
                        "If you are logged into a virtual machine or a remote server "
                        "over SSH, now is a good time to familiarize yourself with "
                        "the concept of entropy and how to make more of it :-)")
            start_time = time.time()
            execute('gpg', '--batch', '--gen-key', gpg_script, logger=logger)
            logger.info("Finished generating GPG key pair in %s.",
                        format_timespan(time.time() - start_time))
            os.unlink(gpg_script)
