# Debian packaging tools: Command line interface
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 17, 2016
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Usage: deb-pkg-tools [OPTIONS] ...

Wrapper for the deb-pkg-tools Python project that implements various tools to
inspect, build and manipulate Debian binary package archives and related
entities like trivial repositories.

Supported options:

  -i, --inspect=FILE

    Inspect the metadata in the Debian binary package archive given by FILE.

  -c, --collect=DIR

    Copy the package archive(s) given as positional arguments (and all packages
    archives required by the given package archives) into the directory given
    by DIR.

  -C, --check=FILE

    Perform static analysis on a package archive and its dependencies in order
    to recognize common errors as soon as possible.

  -p, --patch=FILE

    Patch fields into the existing control file given by FILE. To be used
    together with the -s, --set option.

  -s, --set=LINE

    A line to patch into the control file (syntax: "Name: Value"). To be used
    together with the -p, --patch option.

  -b, --build=DIR

    Build a Debian binary package with `dpkg-deb --build' (and lots of
    intermediate Python magic, refer to the API documentation of the project
    for full details) based on the binary package template in the directory
    given by DIR.

  -u, --update-repo=DIR

    Create or update the trivial Debian binary package repository in the
    directory given by DIR.

  -a, --activate-repo=DIR

    Enable `apt-get' to install packages from the trivial repository (requires
    root/sudo privilege) in the directory given by DIR. Alternatively you can
    use the -w, --with-repo option.

  -d, --deactivate-repo=DIR

    Cleans up after --activate-repo (requires root/sudo privilege).
    Alternatively you can use the -w, --with-repo option.

  -w, --with-repo=DIR

    Create or update a trivial package repository, activate the repository, run
    the positional arguments as an external command (usually `apt-get install')
    and finally deactivate the repository.

  -y, --yes

    Assume the answer to interactive questions is yes.

  -v, --verbose

    Make more noise! (useful during debugging)

  -h, --help

    Show this message and exit.
"""

# Standard library modules.
import codecs
import functools
import getopt
import logging
import os.path
import shutil
import sys

# External dependencies.
import coloredlogs
from humanfriendly import format_path, format_size
from humanfriendly.text import format, pluralize
from humanfriendly.prompts import prompt_for_confirmation
from humanfriendly.terminal import usage, warning

# Modules included in our package.
from deb_pkg_tools.cache import get_default_cache
from deb_pkg_tools.checks import check_package
from deb_pkg_tools.control import patch_control_file
from deb_pkg_tools.package import (build_package, collect_related_packages,
                                   inspect_package, parse_filename)
from deb_pkg_tools.repo import (update_repository,
                                activate_repository,
                                deactivate_repository,
                                with_repository)

# Initialize a logger.
logger = logging.getLogger(__name__)

OUTPUT_ENCODING = 'UTF-8'

def main():
    """
    Command line interface for the ``deb-pkg-tools`` program.
    """
    # Configure logging output.
    coloredlogs.install()
    # Command line option defaults.
    prompt = True
    actions = []
    control_file = None
    control_fields = {}
    # Initialize the package cache.
    cache = get_default_cache()
    # Parse the command line options.
    try:
        options, arguments = getopt.getopt(sys.argv[1:], 'i:c:C:p:s:b:u:a:d:w:yvh', [
            'inspect=', 'collect=', 'check=', 'patch=', 'set=', 'build=',
            'update-repo=', 'activate-repo=', 'deactivate-repo=', 'with-repo=',
            'yes', 'verbose', 'help'
        ])
        for option, value in options:
            if option in ('-i', '--inspect'):
                actions.append(functools.partial(show_package_metadata, archive=value))
            elif option in ('-c', '--collect'):
                actions.append(functools.partial(collect_packages,
                                                 archives=arguments,
                                                 directory=check_directory(value),
                                                 prompt=prompt,
                                                 cache=cache))
                arguments = []
            elif option in ('-C', '--check'):
                actions.append(functools.partial(check_package, archive=value, cache=cache))
            elif option in ('-p', '--patch'):
                control_file = os.path.abspath(value)
                assert os.path.isfile(control_file), "Control file does not exist!"
            elif option in ('-s', '--set'):
                name, _, value = value.partition(':')
                control_fields[name] = value.strip()
            elif option in ('-b', '--build'):
                actions.append(functools.partial(build_package, check_directory(value)))
            elif option in ('-u', '--update-repo'):
                actions.append(functools.partial(update_repository,
                                                 directory=check_directory(value),
                                                 cache=cache))
            elif option in ('-a', '--activate-repo'):
                actions.append(functools.partial(activate_repository, check_directory(value)))
            elif option in ('-d', '--deactivate-repo'):
                actions.append(functools.partial(deactivate_repository, check_directory(value)))
            elif option in ('-w', '--with-repo'):
                actions.append(functools.partial(with_repository_wrapper,
                                                 directory=check_directory(value),
                                                 command=arguments,
                                                 cache=cache))
            elif option in ('-y', '--yes'):
                prompt = False
            elif option in ('-v', '--verbose'):
                coloredlogs.increase_verbosity()
            elif option in ('-h', '--help'):
                usage(__doc__)
                return
        if control_file:
            assert control_fields, "Please specify one or more control file fields to patch!"
            actions.append(functools.partial(patch_control_file, control_file, control_fields))
    except Exception as e:
        warning("Error: %s", e)
        sys.exit(1)
    # Execute the selected action.
    try:
        if actions:
            for action in actions:
                action()
            cache.collect_garbage()
        else:
            usage(__doc__)
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            logger.error("Interrupted by Control-C, aborting!")
        else:
            logger.exception("An error occurred!")
        sys.exit(1)

def show_package_metadata(archive):
    control_fields, contents = inspect_package(archive)
    say("Package metadata from %s:", format_path(archive))
    for field_name in sorted(control_fields.keys()):
        value = control_fields[field_name]
        if field_name == 'Installed-Size':
            value = format_size(int(value) * 1024)
        say(" - %s: %s", field_name, value)
    say("Package contents from %s:", format_path(archive))
    for pathname, entry in sorted(contents.items()):
        size = format_size(entry.size, keep_width=True)
        if len(size) < 10:
            size = ' ' * (10 - len(size)) + size
        if entry.target:
            pathname += ' -> ' + entry.target
        say("{permissions} {owner} {group} {size} {modified} {pathname}",
            permissions=entry.permissions, owner=entry.owner,
            group=entry.group, size=size, modified=entry.modified,
            pathname=pathname)

def collect_packages(archives, directory, prompt=True, cache=None):
    # Find all related packages.
    related_archives = set()
    for filename in archives:
        related_archives.add(parse_filename(filename))
        related_archives.update(collect_related_packages(filename, cache=cache))
    # Ignore package archives that are already in the target directory.
    relevant_archives = set()
    for archive in related_archives:
        basename = os.path.basename(archive.filename)
        if not os.path.isfile(os.path.join(directory, basename)):
            relevant_archives.add(archive)
    # Interactively move the package archives.
    if relevant_archives:
        relevant_archives = sorted(relevant_archives)
        pluralized = pluralize(len(relevant_archives), "package archive", "package archives")
        say("Found %s:", pluralized)
        for file_to_collect in relevant_archives:
            say(" - %s", format_path(file_to_collect.filename))
        prompt_text = "Copy %s to %s?" % (pluralized, format_path(directory))
        if prompt and not prompt_for_confirmation(prompt_text, default=True, padding=False):
            logger.warning("Not copying archive(s) to %s! (aborted by user)", format_path(directory))
        else:
            # Link or copy the file(s).
            for file_to_collect in relevant_archives:
                src = file_to_collect.filename
                dst = os.path.join(directory, os.path.basename(src))
                smart_copy(src, dst)
            logger.info("Done! Copied %s to %s.", pluralized, format_path(directory))

def smart_copy(src, dst):
    """
    Create a hard link to or copy of a file.

    :param src: The pathname of the source file (a string).
    :param dst: The pathname of the target file (a string).

    This function first tries to create a hard link `dst` pointing to `src` and
    if that fails it will perform a regular file copy from `src` to `dst`. This
    is used by :func:`collect_packages()` in an attempt to conserve disk space
    when copying package archives between repositories on the same filesystem.
    """
    try:
        os.link(src, dst)
    except Exception:
        logger.debug("Copying %s -> %s using regular file copy ..", format_path(src), format_path(dst))
        shutil.copy(src, dst)
    else:
        logger.debug("Copied %s -> %s using hard link ..", format_path(src), format_path(dst))

def with_repository_wrapper(directory, command, cache):
    """
    Command line wrapper for :py:func:`deb_pkg_tools.repo.with_repository()`.

    :param directory: The pathname of a directory with ``*.deb`` archives (a
                      string).
    :param command: The command to execute (a list of strings).
    :param cache: The :py:class:`.PackageCache` to use (defaults to ``None``).
    """
    if not command:
        # Default to the user's shell (seems like a sensible default?)
        command = [os.environ.get('SHELL', '/bin/bash')]
    try:
        with_repository(directory, *command, cache=cache)
    except Exception:
        logger.exception("Caught an unhandled exception!")
        sys.exit(1)

def check_directory(argument):
    """
    Make sure a command line argument points to an existing directory.

    :param argument: The original command line argument.
    :returns: The absolute pathname of an existing directory.
    """
    directory = os.path.realpath(os.path.expanduser(argument))
    if not os.path.isdir(directory):
        msg = "Directory doesn't exist! (%s)"
        raise Exception(msg % directory)
    return directory

def say(text, *args, **kw):
    """Reliably print Unicode strings to the terminal / standard output stream."""
    text = format(text, *args, **kw)
    try:
        print(text)
    except UnicodeEncodeError:
        print(codecs.encode(text, OUTPUT_ENCODING))

# vim: ts=4 sw=4 et
