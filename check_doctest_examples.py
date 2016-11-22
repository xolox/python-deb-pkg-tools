#!/usr/bin/env python

"""Quick hack to conditionally evaluate doctest fragments."""

# Standard library modules.
import doctest
import glob
import logging
import os
import sys

# External dependencies.
import coloredlogs
from humanfriendly import format_path

# Modules included in our package.
from deb_pkg_tools.printer import CustomPrettyPrinter

# Initialize a logger.
logger = logging.getLogger('check-doctest-examples')

SAMPLES_DIRECTORY = '/var/lib/deb-pkg-tools/samples'


def main():
    """Command line interface."""
    coloredlogs.install()
    if not os.path.isdir(SAMPLES_DIRECTORY):
        logger.info("Samples directory (%s) doesn't exist, skipping doctest checks ..", SAMPLES_DIRECTORY)
    else:
        failures = 0
        for name in sorted(glob.glob('deb_pkg_tools/*.py')):
            failures += testfile(name, verbose='-v' in sys.argv)
        if failures > 0:
            sys.exit(1)


def testfile(filename, verbose=False):
    """Evaluate and report on the doctest fragments in a single Python file."""
    logger.info("Checking %s", format_path(filename))
    printer = CustomPrettyPrinter()
    filename = os.path.abspath(filename)
    cwd_save = os.getcwd()
    os.chdir(SAMPLES_DIRECTORY)
    results = doctest.testfile(filename=filename,
                               module_relative=False,
                               globs=dict(repr=printer.pformat),
                               optionflags=doctest.NORMALIZE_WHITESPACE,
                               verbose=verbose)
    if results.attempted > 0:
        if results.failed == 0:
            logger.info("Evaluated %i doctests, all passed!", results.attempted)
        else:
            logger.error("Evaluated %i doctests, %i failed!", results.attempted, results.failed)
    os.chdir(cwd_save)
    return results.failed


if __name__ == '__main__':
    main()
