# Debian packaging tools: Command line interface
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: August 7, 2013
# URL: https://github.com/xolox/python-deb-pkg-tools

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
from deb_pkg_tools.package import (inspect_package,
                                   build_package)
from deb_pkg_tools.repo import (update_repository,
                                activate_repository,
                                deactivate_repository)

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
    # Parse the command line options.
    try:
        long_options = ['inspect=', 'build=', 'update-repo=', 'activate-repo=',
                        'deactivate-repo=', 'verbose', 'help']
        options, arguments = getopt.getopt(sys.argv[1:], 'i:b:u:a:d:vh', long_options)
        for option, value in options:
            if option in ('-i', '--inspect'):
                actions.append(functools.partial(show_package_metadata, value))
            elif option in ('-b', '--build'):
                actions.append(functools.partial(build_package, check_directory(value)))
            elif option in ('-u', '--update-repo'):
                actions.append(functools.partial(update_repository, check_directory(value)))
            elif option in ('-a', '--activate-repo'):
                actions.append(functools.partial(activate_repository, check_directory(value)))
            elif option in ('-d', '--deactivate-repo'):
                actions.append(functools.partial(deactivate_repository, check_directory(value)))
            elif option in ('-v', '--verbose'):
                coloredlogs.increase_verbosity()
            elif option in ('-h', '--help'):
                usage()
                return
    except Exception, e:
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
    except Exception, e:
        logger.exception(e)
        sys.exit(1)

def show_package_metadata(archive):
    control_fields = inspect_package(archive)
    print "Package metadata from %s:" % format_path(archive)
    for field_name in sorted(control_fields.keys()):
        value = control_fields[field_name]
        if field_name == 'Installed-Size':
            value = format_size(int(value) * 1024)
        print " - %s: %s" % (field_name, value)

def check_directory(argument):
    """
    Make sure a command line argument points to an existing directory.

    :param argument: The original command line argument.
    :returns: The absolute pathname of an existing directory.
    """
    directory = os.path.realpath(os.path.expanduser(argument))
    if not os.path.isdir(directory):
        msg = "Repository directory doesn't exist! (%s)"
        raise Exception, msg % directory
    return directory

def usage():
    """
    Print a friendly usage message to the terminal.
    """
    print """
Usage: deb-pkg-tools [OPTIONS]

Supported options:

  -i, --inspect=FILE         inspect the metadata in a *.deb archive
  -b, --build=DIR            build a Debian package with `dpkg-deb --build'
  -u, --update-repo=DIR      create/update a trivial package repository
  -a, --activate-repo=DIR    enable `apt-get' to install packages from a
                             trivial repository (assumes root access)
  -d, --deactivate-repo=DIR  cleans up after --activate-repo
                             (assumes root access)
  -v, --verbose              make more noise
  -h, --help                 show this message and exit
""".strip()

# vim: ts=4 sw=4 et
