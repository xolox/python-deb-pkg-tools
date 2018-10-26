# Debian packaging tools: GPG key pair generation.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: October 26, 2018
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
GPG key pair generation and signing of ``Release`` files.

The :mod:`deb_pkg_tools.gpg` module is used to manage GPG key pairs. It allows
callers to specify which GPG key pair and/or key ID they want to use and will
automatically generate GPG key pairs that don't exist yet.

.. _GnuPG 2.1 compatibility:

GnuPG 2.1 compatibility
-----------------------

In 2018 the :mod:`deb_pkg_tools.gpg` module got a major update to enable
compatibility with GnuPG >= 2.1:

- The :mod:`deb_pkg_tools.gpg` module was first integrated into deb-pkg-tools
  in 2013 and was developed based on GnuPG 1.4.10 which was the version
  included in Ubuntu 10.04.

- Ubuntu 18.04 includes GnuPG 2.2.4 which differs from 1.4.10 in several
  backwards incompatible ways that require changes in deb-pkg-tools which
  directly affect the users of deb-pkg-tools (the API has changed).

The following sections discuss the concrete changes:

.. contents::
   :local:

Storage of secret keys
~~~~~~~~~~~~~~~~~~~~~~

The storage of secret keys has changed in a backwards incompatible way, such
that the ``--secret-keyring`` command line option is now obsolete and ignored.
The GnuPG documentation suggests to use an `ephemeral home directory`_ as a
replacement for ``--secret-keyring``. To enable compatibility with GnuPG >= 2.1
while at the same time preserving compatibility with older releases, the
:class:`GPGKey` class gained a new :attr:`~GPGKey.directory` property:

- When GnuPG >= 2.1 is detected :attr:`~GPGKey.directory` is required.

- When GnuPG < 2.1 is detected :attr:`~GPGKey.directory` may be specified and
  will be respected, but you can also use "the old calling convention" where
  the :attr:`~GPGKey.public_key_file`, :attr:`~GPGKey.secret_key_file` and
  :attr:`~GPGKey.key_id` properties are specified separately.

- The documentation of the :class:`GPGKey` initializer explains how to enable
  compatibility with old and new versions GnuPG versions at the same time
  (using the same Python code).

Unattended key generation
~~~~~~~~~~~~~~~~~~~~~~~~~

The default behavior of ``gpg --batch --gen-key`` has changed:

- The user is now presented with a GUI prompt that asks to specify a pass
  phrase for the new key, at which point the supposedly unattended key
  generation is effectively blocked on user input...

- To avoid the GUI prompt the new ``%no-protection`` option needs to be added
  to the batch file, but of course that option will not be recognized by older
  GnuPG releases, so it needs to be added conditionally.

.. _ephemeral home directory: https://www.gnupg.org/documentation/manuals/gnupg/Ephemeral-home-directories.html#Ephemeral-home-directories
"""

# Standard library modules.
import logging
import multiprocessing
import os.path
import tempfile

# External dependencies.
from executor import execute, quote
from humanfriendly import Timer, coerce_boolean, compact, parse_path
from humanfriendly.decorators import cached
from property_manager import PropertyManager, cached_property, mutable_property

# Modules included in our package.
from deb_pkg_tools.utils import find_installed_version, makedirs
from deb_pkg_tools.version import Version

# Initialize a logger.
logger = logging.getLogger(__name__)

GPG_AGENT_VARIABLE = 'GPG_AGENT_INFO'
"""The name of the environment variable used to communicate between the GPG agent and ``gpg`` processes (a string)."""


def create_directory(pathname):
    """
    Create a GnuPG directory with sane permissions (to avoid GnuPG warnings).

    :param pathname: The directory to create (a string).
    """
    makedirs(pathname)
    os.chmod(pathname, 0o700)


@cached
def have_updated_gnupg():
    """
    Check which version of GnuPG is installed.

    :returns: :data:`True` if GnuPG >= 2.1 is installed,
              :data:`False` for older versions.
    """
    gnupg_version = find_installed_version('gnupg')
    return Version(gnupg_version) >= Version('2.1')


def initialize_gnupg():
    """
    Make sure the ``~/.gnupg`` directory exists.

    Older versions of GPG can/will fail when the ``~/.gnupg`` directory doesn't
    exist (e.g. in a newly created chroot). GPG itself creates the directory
    after noticing that it's missing, but then still fails! Later runs work
    fine however. To avoid this problem we make sure ``~/.gnupg`` exists before
    we run GPG.
    """
    create_directory(parse_path('~/.gnupg'))


class GPGKey(PropertyManager):

    """
    Container for generating GPG key pairs and signing release files.

    This class is used to sign ``Release`` files in Debian package
    repositories. If the given GPG key pair doesn't exist yet it will be
    automatically created without user interaction (except gathering of
    entropy, which is not something I can automate :-).
    """

    def __init__(self, **options):
        """
        Initialize a :class:`GPGKey` object.

        :param options: Refer to the initializer of the superclass
                        (:class:`~property_manager.PropertyManager`)
                        for details about argument handling.

        There are two ways to specify the location of a GPG key pair:

        - The old way applies to GnuPG < 2.1 and uses :attr:`public_key_file`
          and :attr:`secret_key_file`.

        - The new way applies to GnuPG >= 2.1 and uses :attr:`directory`.

        If you don't specify anything the user's default key pair will be used.
        Specifying all three properties enables isolation from the user's
        default keyring that's compatible with old and new GnuPG installations
        at the same time.

        You can also use :attr:`key_id` to select a specific existing GPG key
        pair, possibly in combination with the previously mentioned properties.

        When the caller has specified a custom location for the GPG key pair
        but the associated files don't exist yet a new GPG key pair will be
        automatically generated. This requires that :attr:`name` and
        :attr:`description` have been set.
        """
        # Initialize our superclass.
        super(GPGKey, self).__init__(**options)
        # Initialize ourselves based on the GnuPG version.
        if have_updated_gnupg():
            self.check_new_usage()
        else:
            self.check_old_usage()
            self.set_old_defaults()
            self.check_old_files()
        self.check_key_id()
        self.generate_key_pair()

    def check_key_id(self):
        """Raise :exc:`~exceptions.EnvironmentError` when a key ID has been specified but the key pair doesn't exist."""
        if self.key_id and not self.existing_files:
            raise EnvironmentError(compact(
                "The key ID {key_id} was specified but the configured key pair doesn't exist!",
                key_id=self.key_id,
            ))

    def check_new_usage(self):
        """
        Raise an exception when detecting a backwards incompatibility.

        :raises: :exc:`~exceptions.TypeError` as described below.

        When GnuPG >= 2.1 is installed the :func:`check_new_usage()` method is
        called to make sure that the caller is aware of the changes in API
        contract that this implies. We do so by raising an exception when both
        of the following conditions hold:

        - The caller is using the old calling convention of setting
          :attr:`public_key_file` and :attr:`secret_key_file` (which
          confirms that the intention is to use an isolated GPG key).

        - The caller is not using the new calling convention of setting
          :attr:`directory` (even though this is required to use an isolated
          GPG key with GnuPG >= 2.1).
        """
        if self.old_usage and not self.new_usage:
            raise TypeError(compact("""
                You're running GnuPG >= 2.1 which requires changes to how
                deb_pkg_tools.gpg.GPGKey is used and unfortunately our
                caller hasn't been updated to support this. Please refer
                to the the deb-pkg-tools 5.0 release notes for details.
            """))

    def check_old_files(self):
        """
        Raise an exception when we risk overwriting an existing public or secret key file.

        :returns: A list of filenames with existing files.
        :raises: :exc:`~exceptions.EnvironmentError` as described below.

        When GnuPG < 2.1 is installed :func:`check_old_files()` is called to
        ensure that when :attr:`public_key_file` and :attr:`secret_key_file`
        have been provided, either both of the files already exist or neither
        one exists. This avoids accidentally overwriting an existing file that
        wasn't generated by deb-pkg-tools and shouldn't be touched at all.
        """
        if len(self.existing_files) == 1:
            raise EnvironmentError(compact(
                "Refusing to overwrite existing key file! ({filename})",
                filename=self.existing_files[0],
            ))

    def check_old_usage(self):
        """
        Raise an exception when either the public or the secret key hasn't been provided.

        :raises: :exc:`~exceptions.TypeError` as described below.

        When GnuPG < 2.1 is installed :func:`check_old_usage()` is called
        to ensure that :attr:`public_key_file` and :attr:`secret_key_file`
        are either both provided or both omitted.
        """
        if self.secret_key_file and not self.public_key_file:
            raise TypeError(compact("""
                The secret key file {filename} was provided without a
                corresponding public key file! Please provide both or
                neither.
            """, filename=self.secret_key_file))
        elif self.public_key_file and not self.secret_key_file:
            raise TypeError(compact("""
                The public key file {filename} was provided without a
                corresponding secret key file! Please provide both or
                neither.
            """, filename=self.public_key_file))

    def generate_key_pair(self):
        """
        Generate a missing GPG key pair on demand.

        :raises: :exc:`~exceptions.TypeError` when the GPG key pair needs to be
                 generated (because it doesn't exist yet) but no :attr:`name`
                 and :attr:`description` were provided.
        """
        logger.debug("Checking if GPG key pair exists ..")
        if self.existing_files:
            logger.debug("Assuming key pair exists (found existing files: %s).", self.existing_files)
            return
        elif not (self.name and self.description):
            raise TypeError("Can't generate GPG key pair without 'name' and 'description'!")
        logger.info("Generating GPG key pair: %s (%s)", self.name, self.description)
        # Make sure all of the required directories exist and have sane
        # permissions (to avoid GnuPG warnings).
        required_dirs = set([self.directory_default, self.directory_effective])
        if not have_updated_gnupg():
            required_dirs.update([
                os.path.dirname(self.public_key_file),
                os.path.dirname(self.public_key_file),
            ])
        for directory in required_dirs:
            create_directory(directory)
        # Use a temporary file for the `gpg --batch --gen-key' batch instructions.
        fd, temporary_file = tempfile.mkstemp(suffix='.txt')
        try:
            with open(temporary_file, 'w') as handle:
                handle.write(self.batch_script)
                handle.write('\n')
            # Inform the operator that this may take a while.
            logger.info(compact("""
                Please note: Generating a GPG key pair can take a long time. If
                you are logged into a virtual machine or a remote server over
                SSH, now is a good time to familiarize yourself with the
                concept of entropy and how to make more of it :-)
            """))
            timer = Timer()
            with EntropyGenerator():
                gen_key_cmd = self.scoped_command
                gen_key_cmd += ['--batch', '--gen-key', temporary_file]
                execute(*gen_key_cmd, logger=logger)
            logger.info("Finished generating GPG key pair in %s.", timer)
        finally:
            os.unlink(temporary_file)
        # Reset cached properties after key generation.
        self.clear_cached_properties()

    def set_old_defaults(self):
        """Fall back to the default public and secret key files for GnuPG < 2.1."""
        if not self.public_key_file and not self.secret_key_file:
            self.public_key_file = os.path.join(self.directory_effective, 'pubring.gpg')
            self.secret_key_file = os.path.join(self.directory_effective, 'secring.gpg')

    @cached_property
    def batch_script(self):
        """A GnuPG batch script suitable for ``gpg --batch --gen-key`` (a string)."""
        logger.debug("Generating batch script for 'gpg --batch --gen-key' ..")
        lines = [
            'Key-Type: RSA',
            'Key-Length: 1024',
            'Subkey-Type: ELG-E',
            'Subkey-Length: 1024',
            'Name-Real: %s' % self.name,
            'Name-Comment: %s' % self.description,
            'Name-Email: none',
            'Expire-Date: 0',
        ]
        if have_updated_gnupg():
            # GnuPG >= 2.1 prompts the operator to pick a password
            # interactively unless '%no-protection' is used. Also
            # %secring has been obsoleted and is now ignored.
            logger.debug("Specializing batch script for GnuPG >= 2.1 ..")
            lines.append('%no-protection')
        else:
            logger.debug("Specializing batch script for GnuPG < 2.1 ..")
            lines.append('%%pubring %s' % self.public_key_file)
            lines.append('%%secring %s' % self.secret_key_file)
        lines.append('%commit')
        text = '\n'.join(lines)
        logger.debug("Here's the complete batch script:\n%s", text)
        return text

    @mutable_property
    def command_name(self):
        """The name of the GnuPG program (a string, defaults to ``gpg``)."""
        return 'gpg'

    @mutable_property
    def description(self):
        """
        The description of the GPG key pair (a string or :data:`None`).

        Used only when the key pair is generated because it doesn't exist yet.
        """

    @mutable_property
    def directory(self):
        """
        The pathname of the GnuPG home directory to use (a string or :data:`None`).

        This property was added in deb-pkg-tools 5.0 to enable compatibility
        with GnuPG >= 2.1 which changed the storage of secret keys in a
        backwards incompatible way by obsoleting the ``--secret-keyring``
        command line option. The GnuPG documentation suggests to use an
        `ephemeral home directory`_ as a replacement and that's why the
        :attr:`directory` property was added.
        """

    @cached_property
    def directory_default(self):
        """The pathname of the default GnuPG home directory (a string)."""
        return parse_path('~/.gnupg')

    @cached_property
    def directory_effective(self):
        """The pathname of the GnuPG home directory that will actually be used (a string)."""
        return self.directory or self.directory_default

    @cached_property
    def existing_files(self):
        """
        A list of strings with the filenames of existing GnuPG data files.

        The content of this list depends on the GnuPG version:

        - On GnuPG >= 2.1 and/or when :attr:`directory` has been set (also on
          GnuPG < 2.1) any files in or below :attr:`directory` are included.

        - On GnuPG < 2.1 :attr:`public_key_file` and :attr:`secret_key_file`
          are included (only if the properties are set and the files exist of
          course).
        """
        filenames = []
        if have_updated_gnupg() or self.new_usage:
            # New usage is mandatory in combination with GnuPG >= 2.1 and
            # optional but supported in combination with GnuPG < 2.1.
            if os.path.isdir(self.directory_effective):
                for root, dirs, files in os.walk(self.directory_effective):
                    filenames.extend(os.path.join(root, fn) for fn in files)
        if self.old_usage and not have_updated_gnupg():
            # Old usage is only possibly in combination with GnuPG < 2.1.
            candidates = (self.public_key_file, self.secret_key_file)
            filenames.extend(fn for fn in candidates if os.path.isfile(fn))
        return filenames

    @cached_property
    def identifier(self):
        """
        A unique identifier for the GPG key pair (a string).

        The output of the ``gpg --list-keys --with-colons`` command is parsed
        to extract a unique identifier for the GPG key pair:

        - When a fingerprint is available this is preferred.
        - Otherwise a long key ID will be returned (assuming one is available).
        - If neither can be extracted :exc:`~exceptions.EnvironmentError` is raised.

        If an isolated key pair is being used the :attr:`directory` option
        should be used instead of the :attr:`public_key_file` and
        :attr:`secret_key_file` properties, even if GnuPG < 2.1 is being used.
        This is necessary because of what appears to be a bug in GnuPG, see
        `this mailing list thread`_ for more discussion.

        .. _this mailing list thread: https://lists.gnupg.org/pipermail/gnupg-users/2002-March/012144.html
        """
        listing = execute(' '.join([self.gpg_command, '--list-keys', '--with-colons']), capture=True)
        parsed_listing = [line.split(':') for line in listing.splitlines()]
        # Look for an 'fpr:*' line with a key fingerprint.
        for fields in parsed_listing:
            if len(fields) >= 10 and fields[0] == 'fpr' and fields[9].isalnum():
                return fields[9]
        # Look for an 'pub:*' line with a long key ID.
        for fields in parsed_listing:
            if len(fields) >= 5 and fields[0] == 'pub' and fields[4].isalnum():
                return fields[4]
        # Explain what went wrong, try to provide hints.
        msg = "Failed to get unique ID of GPG key pair!"
        if self.old_usage and not self.new_usage:
            msg += " Use of the 'directory' option may help to resolve this."
        raise EnvironmentError(msg)

    @property
    def gpg_command(self):
        """
        The GPG command line that can be used to sign using the key, export the key, etc (a string).

        The value of :attr:`gpg_command` is based on :attr:`scoped_command`
        combined with the ``--no-default-keyring``

        The documentation of :func:`GPGKey.__init__()` contains two examples.
        """
        command = self.scoped_command
        if not have_updated_gnupg():
            command.extend((
                '--no-default-keyring',
                '--keyring', self.public_key_file,
                '--secret-keyring', self.secret_key_file,
            ))
        if self.key_id:
            command.extend(('--recipient', self.key_id))
        if self.use_agent:
            command.append('--use-agent')
        return quote(command)

    @mutable_property
    def key_id(self):
        """
        The key ID of an existing key pair to use (a string or :data:`None`).

        If this option is provided then the key pair must already exist.
        """

    @mutable_property
    def name(self):
        """
        The name of the GPG key pair (a string or :data:`None`).

        Used only when the key pair is generated because it doesn't exist yet.
        """

    @property
    def new_usage(self):
        """:data:`True` if the new API is being used, :data:`False` otherwise."""
        return bool(self.directory)

    @property
    def old_usage(self):
        """:data:`True` if the old API is being used, :data:`False` otherwise."""
        return bool(self.public_key_file or self.secret_key_file)

    @mutable_property
    def public_key_file(self):
        """
        The pathname of the public key file (a string or :data:`None`).

        This is only used when GnuPG < 2.1 is installed.
        """

    @property
    def scoped_command(self):
        """
        The GPG program name and optional ``--homedir`` command line option (a list of strings).

        The name of the GPG program is taken from :attr:`command_name` and the
        ``--homedir`` option is only added when :attr:`directory` is set.
        """
        command = [self.command_name]
        if self.directory:
            command.append('--homedir')
            command.append(self.directory)
        return command

    @mutable_property
    def secret_key_file(self):
        """
        The pathname of the secret key file (a string or :data:`None`).

        This is only used when GnuPG < 2.1 is installed.
        """

    @property
    def use_agent(self):
        """
        Whether to enable the use of the `GPG agent`_ (a boolean).

        This property checks whether the environment variable given by
        :data:`GPG_AGENT_VARIABLE` is set to a nonempty value. If it is then
        :attr:`gpg_command` will include the ``--use-agent`` option. This makes
        it possible to integrate repository signing with the GPG agent, so that
        a password is asked for once instead of every time something is signed.

        .. _GPG agent: http://linux.die.net/man/1/gpg-agent
        """
        return bool(os.environ.get(GPG_AGENT_VARIABLE))


class EntropyGenerator(object):

    """
    Force the system to generate entropy based on disk I/O.

    The `deb-pkg-tools` test suite runs on Travis CI which uses virtual
    machines to isolate tests. Because the `deb-pkg-tools` test suite generates
    several GPG keys it risks the chance of getting stuck and being killed
    after 10 minutes of inactivity. This happens because of a lack of entropy
    which is a very common problem in virtualized environments.
    There are tricks to use fake entropy to avoid this problem:

    - The `rng-tools` package/daemon can feed ``/dev/random`` based on
      ``/dev/urandom``. Unfortunately this package doesn't work on Travis CI
      because they use OpenVZ which uses read only ``/dev/random`` devices.

    - GPG version 2 supports the ``--debug-quick-random`` option but I haven't
      investigated how easy it is to switch.

    Instances of this class can be used as a context manager to generate
    endless disk I/O which is one of the few sources of entropy on virtualized
    systems. Entropy generation is enabled when the environment variable
    ``$DPT_FORCE_ENTROPY`` is set to ``yes``, ``true`` or ``1``.
    """

    def __init__(self):
        """Initialize a :class:`EntropyGenerator` object."""
        self.enabled = coerce_boolean(os.environ.get('DPT_FORCE_ENTROPY', 'false'))
        if self.enabled:
            self.process = multiprocessing.Process(target=generate_entropy)

    def __enter__(self):
        """Enable entropy generation."""
        if self.enabled:
            logger.warning("Forcing entropy generation using disk I/O, performance will suffer ..")
            self.process.start()

    def __exit__(self, exc_type, exc_value, traceback):
        """Disable entropy generation."""
        if self.enabled:
            self.process.terminate()
            logger.debug("Terminated entropy generation.")


def generate_entropy():
    """
    Force the system to generate entropy based on disk I/O.

    This function is run in a separate process by :class:`EntropyGenerator`.
    It scans the complete file system and reads every file it finds in blocks
    of 1 KB. This function never returns; it has to be killed.
    """
    # Continue until we are killed.
    while True:
        # Scan the complete file system.
        for root, dirs, files in os.walk('/'):
            for filename in files:
                pathname = os.path.join(root, filename)
                # Don't try to read device files, named pipes, etc.
                if os.path.isfile(pathname):
                    # Read every file on the file system in blocks of 1 KB.
                    try:
                        with open(pathname) as handle:
                            while True:
                                block = handle.read(1024)
                                if not block:
                                    break
                    except Exception:
                        pass
