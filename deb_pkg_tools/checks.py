# Debian packaging tools: Static analysis of package archives.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 21, 2016
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Static analysis of Debian binary packages to detect common problems.

The :class:`deb_pkg_tools.checks` module attempts to detect common problems in
Debian binary package archives using static analysis. Currently there's a check
that detects duplicate files in dependency sets and a check that detects
version conflicts in repositories.
"""

# Standard library modules.
import collections
import itertools
import logging

# External dependencies.
from humanfriendly import format_path, pluralize, Spinner, Timer
from humanfriendly.text import compact

# Modules included in our package.
from deb_pkg_tools.package import collect_related_packages, inspect_package, parse_filename
from deb_pkg_tools.utils import optimize_order

# Initialize a logger.
logger = logging.getLogger(__name__)


def check_package(archive, cache=None):
    """
    Perform static checks on a package's dependency set.

    :param archive: The pathname of an existing ``*.deb`` archive (a string).
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :raises: :exc:`BrokenPackage` when one or more checks failed.
    """
    timer = Timer()
    logger.info("Checking %s ..", format_path(archive))
    dependency_set = collect_related_packages(archive, cache=cache)
    failed_checks = []
    # Check for duplicate files in the dependency set.
    try:
        check_duplicate_files(dependency_set, cache=cache)
    except BrokenPackage as e:
        failed_checks.append(e)
    except ValueError:
        # Silenced.
        pass
    # Check for version conflicts in the dependency set.
    try:
        check_version_conflicts(dependency_set, cache=cache)
    except BrokenPackage as e:
        failed_checks.append(e)
    if len(failed_checks) == 1:
        raise failed_checks[0]
    elif failed_checks:
        raise BrokenPackage('\n\n'.join(map(str, failed_checks)))
    else:
        logger.info("Finished checking in %s, no problems found.", timer)


def check_duplicate_files(dependency_set, cache=None):
    """
    Check a collection of Debian package archives for conflicts.

    :param dependency_set: A list of filenames (strings) of ``*.deb`` files.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :raises: :exc:`exceptions.ValueError` when less than two package
             archives are given (the duplicate check obviously only works if
             there are packages to compare :-).
    :raises: :exc:`DuplicateFilesFound` when duplicate files are found
             within a group of package archives.

    This check looks for duplicate files in package archives that concern
    different packages. Ignores groups of packages that have their 'Provides'
    and 'Replaces' fields set to a common value. Other variants of 'Conflicts'
    are not supported yet.

    Because this analysis involves both the package control file fields and the
    pathnames of files installed by packages it can be really slow. To make it
    faster you can use the :class:`.PackageCache`.
    """
    timer = Timer()
    dependency_set = list(map(parse_filename, dependency_set))
    # Make sure we have something useful to work with.
    num_archives = len(dependency_set)
    if num_archives < 2:
        msg = "To check for duplicate files you need to provide two or more packages archives! (%i given)"
        raise ValueError(msg % num_archives)
    # Build up a global map of all files contained in the given package archives.
    global_contents = collections.defaultdict(set)
    global_fields = {}
    spinner = Spinner(total=num_archives)
    logger.info("Checking for duplicate files in %i package archives ..", num_archives)
    for i, archive in enumerate(optimize_order(dependency_set), start=1):
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
        summary.append(compact("""
            Hint: If the package contents are correct you can resolve these
            conflicts by marking the packages as conflicting. You do this by
            adding the 'Conflicts' and 'Provides' fields and setting them to a
            common value. That should silence this message.
        """))
        delimiter = '%s\n' % ('-' * 79)
        raise DuplicateFilesFound(delimiter.join(summary))
    else:
        logger.info("No conflicting files found (took %s).", timer)


def check_version_conflicts(dependency_set, cache=None):
    """
    Check for version conflicts in a dependency set.

    :param dependency_set: A list of filenames (strings) of ``*.deb`` files.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :raises: :exc:`VersionConflictFound` when one or more version
             conflicts are found.

    For each Debian binary package archive given, check if a newer version of
    the same package exists in the same repository (directory). This analysis
    can be very slow. To make it faster you can use the
    :class:`.PackageCache`.
    """
    timer = Timer()
    summary = []
    dependency_set = list(map(parse_filename, dependency_set))
    spinner = Spinner(total=len(dependency_set))
    logger.info("Checking for version conflicts in %i package(s) ..", len(dependency_set))
    for i, archive in enumerate(dependency_set, start=1):
        if archive.newer_versions:
            summary.append(compact("""
                    Dependency set includes {dependency} but newer version(s)
                    of that package also exist and will take precedence:
            """, dependency=format_path(archive.filename)))
            summary.append("\n".join(" - %s" % format_path(a.filename) for a in sorted(archive.newer_versions)))
        spinner.step(label="Checking for version conflicts", progress=i)
    spinner.clear()
    if summary:
        summary.insert(0, "One or more version conflicts found:")
        raise VersionConflictFound('\n\n'.join(summary))
    else:
        logger.info("No version conflicts found (took %s).", timer)


class BrokenPackage(Exception):

    """Base class for exceptions raised by the checks defined in :mod:`deb_pkg_tools.checks`."""


class DuplicateFilesFound(BrokenPackage):

    """Raised by :func:`check_duplicate_files()` when duplicates are found."""


class VersionConflictFound(BrokenPackage):

    """Raised by :func:`check_version_conflicts()` when version conflicts are found."""
