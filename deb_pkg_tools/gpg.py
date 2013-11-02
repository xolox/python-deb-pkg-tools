# Debian packaging tools: GPG key pair generation.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 2, 2013
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
GPG key pair handling
=====================

This module is used to manage GPG key pairs. It allows callers to specify which
GPG key pair and/or key ID they want to use and will automatically generate GPG
key pairs that don't exist yet.
"""

# Standard library modules.
import logging
import os.path
import pipes
import tempfile
import textwrap
import time

# External dependencies.
from humanfriendly import format_path, format_timespan

# Modules included in our package.
from deb_pkg_tools.utils import execute, find_home_directory

# Initialize a logger.
logger = logging.getLogger(__name__)

def initialize_gnupg():
    """
    Older versions of GPG can/will fail when the ``~/.gnupg`` directory doesn't
    exist (e.g. in a newly created chroot). GPG itself creates the directory
    after noticing that it's missing, but then still fails! Later runs work
    fine however. To avoid this problem we make sure ``~/.gnupg`` exists before
    we run GPG.
    """
    gnupg_directory = os.path.join(find_home_directory(), '.gnupg')
    if not os.path.isdir(gnupg_directory):
        logger.debug("The directory %s doesn't exist yet! I'll create it now before we call GPG to make sure GPG won't complain ..")
        os.makedirs(gnupg_directory)

class GPGKey(object):

    """
    Container for GPG key pairs that can be used to automatically sign
    ``Release`` files in Debian package repositories. If the given GPG key pair
    doesn't exist yet it will be automatically created without user interaction
    (except gathering of entropy, which is not something I can automate :-).
    """

    def __init__(self, name=None, description=None, secret_key_file=None, public_key_file=None, key_id=None):
        """
        Initialize a GPG key object in one of several ways:

        1. If `key_id` is specified then the GPG key must have been created
           previously. If `secret_key_file` and `public_key_file` are not
           specified they default to ``~/.gnupg/secring.gpg`` and
           ``~/.gnupg/pubring.gpg``. In this case `key_id` is the only
           required argument.

           The following example assumes that the provided GPG key ID is
           defined in the default keyring of the current user:

           >>> from deb_pkg_tools.gpg import GPGKey
           >>> key = GPGKey(key_id='58B6B02B')
           >>> key.gpg_command
           'gpg --no-default-keyring --secret-keyring /home/peter/.gnupg/secring.gpg --keyring /home/peter/.gnupg/pubring.gpg --recipient 58B6B02B'

        2. If `secret_key_file` and `public_key_file` are specified but the
           files don't exist yet, a GPG key will be generated for you. In this
           case `name` and `description` are required arguments and `key_id`
           must be ``None`` (the default). An example:

           >>> name = 'deb-pkg-tools'
           >>> description = 'Automatic signing key for deb-pkg-tools'
           >>> secret_key_file = '/home/peter/.deb-pkg-tools/automatic-signing-key.sec'
           >>> public_key_file = '/home/peter/.deb-pkg-tools/automatic-signing-key.pub'
           >>> key = GPGKey(name, description, secret_key_file, public_key_file)
           >>> key.gpg_command
           'gpg --no-default-keyring --secret-keyring /home/peter/.deb-pkg-tools/automatic-signing-key.sec --keyring /home/peter/.deb-pkg-tools/automatic-signing-key.pub'

        :param name: The name of the GPG key pair (a string). Used only when
                     the key pair is generated because it doesn't exist yet.
        :param description: The description of the GPG key pair (a string).
                            Used only when the key pair is generated because it
                            doesn't exist yet.
        :param secret_key_file: The absolute pathname of the secret key file (a
                                string). Defaults to ``~/.gnupg/secring.gpg``.
        :param public_key_file: The absolute pathname of the public key file (a
                                string). Defaults to ``~/.gnupg/pubring.gpg``.
        :param key_id: The key ID of an existing key pair to use (a string). If
                       this argument is provided then the key pair's secret and
                       public key files must already exist.
        """

        # If the secret or public key file is provided, the other key file must
        # be provided as well.
        if secret_key_file and not public_key_file:
            raise Exception, "You provided a GPG secret key file without a public key file; please provide both!"
        elif public_key_file and not secret_key_file:
            raise Exception, "You provided a GPG public key file without a secret key file; please provide both!"

        # If neither of the key files is provided we'll default to the
        # locations that GnuPG uses by default.
        if not secret_key_file and not public_key_file:
            gnupg_directory = os.path.join(find_home_directory(), '.gnupg')
            secret_key_file = os.path.join(gnupg_directory, 'secring.gpg')
            public_key_file = os.path.join(gnupg_directory, 'pubring.gpg')

        # If a key ID was specified then the two key files must already exist;
        # we won't generate them because that makes no sense :-)
        if key_id and not os.path.isfile(secret_key_file):
            text = "The provided GPG secret key file (%s) doesn't exist but a key ID was specified!"
            raise Exception, text % secret_key_file
        if key_id and not os.path.isfile(public_key_file):
            text = "The provided GPG public key file (%s) doesn't exist but a key ID was specified!"
            raise Exception, text % public_key_file

        # If we're going to generate a GPG key for the caller we don't want to
        # overwrite a secret or public key file without its counterpart. We'll
        # also need a name and description for the generated key.
        existing_files = filter(os.path.isfile, [secret_key_file, public_key_file])
        if len(existing_files) not in (0, 2):
            text = "Refusing to overwrite existing key file! (%s)"
            raise Exception, text % existing_files[0]
        elif len(existing_files) == 0 and not (name and description):
            raise Exception, "To generate a GPG key you must provide a name and description!"

        # Store the arguments.
        self.name = name
        self.description = description
        self.secret_key_file = secret_key_file
        self.public_key_file = public_key_file
        self.key_id = key_id

        # Generate the GPG key pair if required.
        if not existing_files:

            # Make sure the directories of the secret/public key files exist.
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
            initialize_gnupg()
            execute('gpg', '--batch', '--gen-key', gpg_script, logger=logger)
            logger.info("Finished generating GPG key pair in %s.",
                        format_timespan(time.time() - start_time))
            os.unlink(gpg_script)

    @property
    def gpg_command(self):
        """
        The GPG command line that can be used to sign using the key, export the
        key, etc. The documentation of :py:func:`GPGKey.__init__()` contains
        two examples.
        """
        command = ['gpg', '--no-default-keyring',
                   '--secret-keyring', pipes.quote(self.secret_key_file),
                   '--keyring', pipes.quote(self.public_key_file)]
        if self.key_id:
            command.extend(['--recipient', self.key_id])
        return ' '.join(command)
