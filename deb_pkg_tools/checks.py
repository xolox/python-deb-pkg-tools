# Debian packaging tools: Static analysis of package archives.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: June 9, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Static analysis of package archives
===================================
"""

# Standard library modules.
import collections
import itertools
import logging

# External dependencies.
from deb_pkg_tools.package import inspect_package, parse_filename
from deb_pkg_tools.utils import optimize_order
from humanfriendly import pluralize, Spinner

# Initialize a logger.
logger = logging.getLogger(__name__)

def check_duplicate_files(package_archives, cache=None):
    """
    Check a collection of Debian package archives for conflicts.

    Looks for duplicate files in unrelated package archives. Ignores groups of
    packages that have their 'Provides' and 'Replaces' fields set to a common
    value. Other variants of 'Conflicts' are not supported yet.

    Because this analysis involves both the package control file fields and the
    pathnames of files installed by packages it can be slow. To make it faster
    you can use the :py:class:`.PackageCache`.

    :param package_archives: A list of filenames (strings) of ``*.deb`` files.
    :param cache: The :py:class:`.PackageCache` to use (defaults to ``None``).
    :raises: :py:class:`exceptions.ValueError` when less than two package
             archives are given (the duplicate check obviously only works if
             there are packages to compare :-).
    """
    package_archives = list(map(parse_filename, package_archives))
    # Make sure we have something useful to work with.
    num_archives = len(package_archives)
    if num_archives < 2:
        msg = "To check for duplicate files you need to provide two or more packages archives! (%i given)"
        raise ValueError(msg % num_archives)
    # Build up a global map of all files contained in the given package archives.
    global_contents = collections.defaultdict(set)
    global_fields = {}
    spinner = Spinner(total=num_archives)
    logger.info("Scanning %i package archives for duplicate files (this can take a while) ..", num_archives)
    for i, archive in enumerate(optimize_order(package_archives), start=1):
        spinner.step(label="Scanning %i package archives" % num_archives, progress=i)
        fields, contents = inspect_package(archive.filename, cache=cache)
        global_fields[archive.filename] = fields
        for pathname, stat in contents.items():
            if not stat.permissions.startswith('d'):
                global_contents[pathname].add(archive)
    spinner.clear()
    # Count the number of duplicate files between sets of conflicting packages
    # for more user friendly reporting.
    duplicate_files = collections.defaultdict(lambda: dict(count=0, filenames=[]))
    for pathname, packages in global_contents.items():
        if len(packages) > 1:
            # Override the sort key to be the filename because we don't need
            # to properly sort by version (which is slow on large collections).
            key = tuple(sorted(packages, key=lambda p: p.filename))
            duplicate_files[key]['count'] += 1
            duplicate_files[key]['filenames'].append(pathname)
    for packages, information in sorted(duplicate_files.items()):
        # Never report multiple versions of the same package.
        if len(set(package.name for package in packages)) == 1:
            duplicate_files.pop(packages)
            continue
        # We check for one common case where it's easy to guarantee that
        # we're not dealing with broken packages: All of the packages have
        # marked each other as conflicting via the combination of the
        # fields `Provides:' and `Conflicts:'.
        def find_virtual_name(field_name):
            package_names = set()
            for archive in packages:
                field = global_fields[archive.filename].get(field_name)
                if field:
                    package_names |= field.names
                else:
                    return
            if len(package_names) == 1:
                return list(package_names)[0]
        marked_conflicts = find_virtual_name('Conflicts')
        marked_provides = find_virtual_name('Provides')
        if marked_conflicts and marked_conflicts == marked_provides:
            duplicate_files.pop(packages)
    # Boring string formatting, trying to find a way to clearly present conflicts.
    summary = []
    for packages, information in sorted(duplicate_files.items()):
            block = []
            conflicts = pluralize(information['count'], 'conflict', 'conflicts')
            block.append("Found %s between %i packages:\n" % (conflicts, len(packages)))
            for i, package in enumerate(sorted(packages), start=1):
                block.append("  %i. %s\n" % (i, package.filename))
            block.append("These packages contain %s:\n" % conflicts)
            for i, filename in enumerate(sorted(information['filenames']), start=1):
                block.append("  %i. %s\n" % (i, filename))
            summary.append(''.join(block))
    if summary:
        archives_involved = set(itertools.chain.from_iterable(duplicate_files.keys()))
        files = pluralize(len(duplicate_files), 'duplicate file', 'duplicate files')
        archives = pluralize(len(archives_involved), 'package archive', 'package archives')
        summary.insert(0, "Found %s in %s!\n" % (files, archives))
        summary.append("Hint: If the package contents are correct you can resolve these conflicts by\n"
                       "marking the packages as conflicting. You do this by adding the 'Conflicts' and\n"
                       "'Provides' fields and setting them to a common value. That should silence this\n"
                       "message.")
        delimiter = '%s\n' % ('-' * 79)
        raise DuplicateFilesFound(delimiter.join(summary))
    else:
        logger.info("No conflicting files found in %i package(s).", len(package_archives))

class DuplicateFilesFound(Exception):
    """
    Raised by :py:func:`check_duplicate_files()` when duplicates are found.
    """

# vim: ts=4 sw=4 et
