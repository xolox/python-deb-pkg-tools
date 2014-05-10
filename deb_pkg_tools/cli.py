# Debian packaging tools: Command line interface
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 10, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Usage: deb-pkg-tools [OPTIONS]

Supported options:

  -i, --inspect=FILE          inspect the metadata in a *.deb archive
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
  -v, --verbose               make more noise
  -h, --help                  show this message and exit
"""

# Standard library modules.
import functools
import getopt
import logging
import os.path
import sys

# External dependencies.
import coloredlogs
from humanfriendly import format_path, format_size

# Modules included in our package.
from deb_pkg_tools.control import patch_control_file
from deb_pkg_tools.package import inspect_package, build_package
from deb_pkg_tools.repo import (update_repository,
                                activate_repository,
                                deactivate_repository,
                                with_repository)

# Initialize a logger.
logger = logging.getLogger(__name__)

def main():
    """
    Command line interface for the ``deb-pkg-tools`` program.
    """
    # Configure logging output.
    coloredlogs.install()
    # Command line option defaults.
    actions = []
    control_file = None
    control_fields = {}
    # Parse the command line options.
    try:
        long_options = ['inspect=', 'patch=', 'set=', 'build=', 'update-repo=',
                        'activate-repo=', 'deactivate-repo=', 'with-repo=',
                        'verbose', 'help']
        options, arguments = getopt.getopt(sys.argv[1:], 'i:p:s:b:u:a:d:w:vh', long_options)
        for option, value in options:
            if option in ('-i', '--inspect'):
                actions.append(functools.partial(show_package_metadata, value))
            elif option in ('-p', '--patch'):
                control_file = os.path.abspath(value)
                assert os.path.isfile(control_file), "Control file does not exist!"
            elif option in ('-s', '--set'):
                name, _, value = value.partition(':')
                control_fields[name] = value.strip()
            elif option in ('-b', '--build'):
                actions.append(functools.partial(build_package, check_directory(value)))
            elif option in ('-u', '--update-repo'):
                actions.append(functools.partial(update_repository, check_directory(value)))
            elif option in ('-a', '--activate-repo'):
                actions.append(functools.partial(activate_repository, check_directory(value)))
            elif option in ('-d', '--deactivate-repo'):
                actions.append(functools.partial(deactivate_repository, check_directory(value)))
            elif option in ('-w', '--with-repo'):
                actions.append(functools.partial(with_repository_wrapper, check_directory(value), arguments))
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
        else:
            usage()
    except Exception as e:
        logger.exception(e)
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
        print(entry.permissions, '%s/%s' % (entry.owner, entry.group), size, entry.modified, pathname)

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

def with_repository_wrapper(directory, command):
    """
    Command line wrapper for :py:func:`deb_pkg_tools.repo.with_repository()`.

    :param directory: The pathname of a directory with ``*.deb`` archives (a
                      string).
    :param command: The command to execute (a list of strings).
    """
    if not command:
        # Default to the user's shell (seems like a sensible default?)
        command = [os.environ.get('SHELL', '/bin/bash')]
    try:
        with_repository(directory, *command)
    except Exception:
        logger.exception("Caught an unhandled exception!")
        sys.exit(1)

def usage():
    """
    Print a friendly usage message to the terminal.
    """
    print(__doc__.strip())

# vim: ts=4 sw=4 et
