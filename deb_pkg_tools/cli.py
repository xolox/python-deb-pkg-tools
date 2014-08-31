# Debian packaging tools: Command line interface
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: August 31, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Usage: deb-pkg-tools [OPTIONS] ...

Supported options:

  -i, --inspect=FILE          inspect the metadata in a *.deb archive
  -c, --collect=DIR           copy the package archive(s) given as positional
                              arguments and all packages archives required by
                              the given package archives into a directory
  -C, --check=FILE            perform static analysis on a package archive and
                              its dependencies in order to recognize common
                              errors as soon as possible
  -p, --patch=FILE            patch fields into an existing control file
  -s, --set=LINE              a line to patch into the control file
                              (syntax: "Name: Value")
  -b, --build=DIR             build a Debian package with `dpkg-deb --build'
  -u, --update-repo=DIR       create/update a trivial package repository
  -a, --activate-repo=DIR     enable `apt-get' to install packages from a
                              trivial repository (requires root/sudo privilege)
  -d, --deactivate-repo=DIR   cleans up after --activate-repo
                              (requires root/sudo privilege)
  -w, --with-repo=DIR CMD...  create/update a trivial package repository,
                              activate the repository, run the positional
                              arguments as an external command (usually `apt-get
                              install') and finally deactivate the repository
  -y, --yes                   assume the answer to interactive questions is yes
  -v, --verbose               make more noise
  -h, --help                  show this message and exit
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
from humanfriendly import format_path, format_size, pluralize

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
    # Enable printing of Unicode strings even when our standard output and/or
    # standard error streams are not connected to a terminal. This is required
    # on Python 2.x but will break on Python 3.x which explains the ugly
    # version check. See also: http://stackoverflow.com/q/4374455/788200.
    if sys.version_info[0] == 2:
        sys.stdout = codecs.getwriter(OUTPUT_ENCODING)(sys.stdout)
        sys.stderr = codecs.getwriter(OUTPUT_ENCODING)(sys.stderr)
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
                usage()
                return
        if control_file:
            assert control_fields, "Please specify one or more control file fields to patch!"
            actions.append(functools.partial(patch_control_file, control_file, control_fields))
    except Exception as e:
        logger.error(e)
        print
        usage()
        sys.exit(1)
    # Execute the selected action.
    try:
        if actions:
            for action in actions:
                action()
            cache.collect_garbage()
        else:
            usage()
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            logger.error("Interrupted by Control-C, aborting!")
        else:
            logger.exception("An error occurred!")
        sys.exit(1)

def show_package_metadata(archive):
    control_fields, contents = inspect_package(archive)
    print("Package metadata from %s:" % format_path(archive))
    for field_name in sorted(control_fields.keys()):
        value = control_fields[field_name]
        if field_name == 'Installed-Size':
            value = format_size(int(value) * 1024)
        print(" - %s: %s" % (field_name, value))
    print("Package contents from %s:" % format_path(archive))
    for pathname, entry in sorted(contents.items()):
        size = format_size(entry.size, keep_width=True)
        if len(size) < 10:
            size = ' ' * (10 - len(size)) + size
        if entry.target:
            pathname += ' -> ' + entry.target
        print("{permissions} {owner} {group} {size} {modified} {pathname}".format(
            permissions=entry.permissions, owner=entry.owner,
            group=entry.group, size=size, modified=entry.modified,
            pathname=pathname))

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
        print("Found %s:" % pluralized)
        for file_to_collect in relevant_archives:
            print(" - %s" % format_path(file_to_collect.filename))
        try:
            if prompt:
                # Ask permission to copy the file(s).
                prompt = "Copy %s to %s? [Y/n] " % (pluralized, format_path(directory))
                assert raw_input(prompt).lower() in ('', 'y', 'yes')
            # Copy the file(s).
            for file_to_collect in relevant_archives:
                copy_from = file_to_collect.filename
                copy_to = os.path.join(directory, os.path.basename(copy_from))
                logger.debug("Copying %s -> %s ..", format_path(copy_from), format_path(copy_to))
                shutil.copy(copy_from, copy_to)
            logger.info("Done! Copied %s to %s.", pluralized, format_path(directory))
        except (AssertionError, KeyboardInterrupt, EOFError) as e:
            if isinstance(e, KeyboardInterrupt):
                # Control-C interrupts the prompt without emitting a newline. We'll
                # print one manually so the console output doesn't look funny.
                sys.stderr.write('\n')
            logger.warning("Not copying archive(s) to %s! (aborted by user)", format_path(directory))
            if isinstance(e, KeyboardInterrupt):
                # Maybe we shouldn't actually swallow Control-C, it can make
                # for a very unfriendly user experience... :-)
                raise

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

def usage():
    """
    Print a friendly usage message to the terminal.
    """
    print(__doc__.strip())

# vim: ts=4 sw=4 et
