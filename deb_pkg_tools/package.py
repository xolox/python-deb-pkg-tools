# Debian packaging tools: Package manipulation.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 11, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""Functions to build and inspect Debian binary package archives (``*.deb`` files)."""

# Standard library modules.
import collections
import copy
import fnmatch
import logging
import os
import os.path
import pipes
import random
import re
import shutil
import tempfile

# External dependencies.
from executor import CommandNotFound, ExternalCommandFailed, execute
from humanfriendly import coerce_boolean, format_path, Timer
from humanfriendly.text import concatenate, pluralize
from humanfriendly.terminal.spinners import Spinner

# Modules included in our package.
from deb_pkg_tools.deb822 import parse_deb822
from deb_pkg_tools.control import parse_control_fields, patch_control_file
from deb_pkg_tools.utils import makedirs
from deb_pkg_tools.version import Version

# Public identifiers that require documentation.
__all__ = (
    "ALLOW_CHOWN",
    "ALLOW_FAKEROOT_OR_SUDO",
    "ALLOW_HARD_LINKS",
    "ALLOW_RESET_SETGID",
    "ArchiveEntry",
    "BINARY_PACKAGE_ARCHIVE_EXTENSIONS",
    "CollectedPackagesConflict",
    "DEPENDENCY_FIELDS",
    "DIRECTORIES_TO_REMOVE",
    "FILES_TO_REMOVE",
    "OBJECT_FILE_EXCLUDES",
    "PARSE_STRICT",
    "PackageFile",
    "ROOT_GROUP",
    "ROOT_USER",
    "build_package",
    "clean_package_tree",
    "collect_related_packages",
    "collect_related_packages_helper",
    "copy_package_files",
    "determine_package_archive",
    "find_latest_version",
    "find_object_files",
    "find_package_archives",
    "find_system_dependencies",
    "group_by_latest_versions",
    "inspect_package",
    "inspect_package_contents",
    "inspect_package_fields",
    "is_binary_file",
    "logger",
    "match_relationships",
    "parse_filename",
    "strip_object_files",
    "update_conffiles",
    "update_installed_size",
)

# Initialize a logger.
logger = logging.getLogger(__name__)

BINARY_PACKAGE_ARCHIVE_EXTENSIONS = ('.deb', '.udeb')
"""
A tuple of strings with supported filename extensions of Debian binary package
archives. Used by :func:`find_package_archives()` and :func:`parse_filename()`.
"""

DEPENDENCY_FIELDS = ('Depends', 'Pre-Depends')
"""
A tuple of strings with names of control file fields that specify dependencies,
used by :func:`collect_related_packages()` to analyze dependency trees.
"""

DIRECTORIES_TO_REMOVE = (
    '.bzr',         # Bazaar (version control system).
    '.git',         # Git (version control system).
    '.hg',          # Mercurial (version control system).
    '.svn',         # SVN (version control system).
    '__pycache__',  # Python 3 byte code files.
)
"""
A tuple of strings with :mod:`fnmatch` patterns of directories to remove before
building a package. Used by :func:`clean_package_tree()` which is called by
:func:`build_package()`. Avoids the following Lintian warnings:

- `package-contains-vcs-control-dir <http://lintian.debian.org/tags/package-contains-vcs-control-dir.html>`_
- `package-installs-python-pycache-dir <http://lintian.debian.org/tags/package-installs-python-pycache-dir.html>`_
"""

FILES_TO_REMOVE = (
    '*.pyc',             # Python byte code files.
    '*.pyo',             # Python optimized byte code files.
    '*~',                # Backups created by text editors (Emacs/Vim).
    '.*.s??',            # Vim named swap files.
    '.DS_Store',         # Mac OS X custom folder attributes.
    '.DS_Store.gz',      # Mac OS X custom folder attributes.
    '._*',               # Mac OS X resource forks.
    '.bzrignore',        # Bazaar ignore files.
    '.gitignore',        # Git ignore files.
    '.hg_archival.txt',  # Artefact of `hg archive'.
    '.hgignore',         # Mercurial ignore files.
    '.hgtags',           # Mercurial tags files.
    '.s??',              # Vim anonymous swap files.
)
"""
A tuple of strings with :mod:`fnmatch` patterns of files to remove before
building a package. Used by :func:`clean_package_tree()` which is called by
:func:`build_package()`. Avoids the following Lintian warnings:

- `backup-file-in-package <http://lintian.debian.org/tags/backup-file-in-package.html>`_
- `macos-ds-store-file-in-package <http://lintian.debian.org/tags/macos-ds-store-file-in-package.html>`_
- `macos-resource-fork-file-in-package <http://lintian.debian.org/tags/macos-resource-fork-file-in-package.html>`_
- `package-contains-vcs-control-file <http://lintian.debian.org/tags/package-contains-vcs-control-file.html>`_
- `package-installs-python-bytecode <http://lintian.debian.org/tags/package-installs-python-bytecode.html>`_
"""

OBJECT_FILE_EXCLUDES = (
    '*.eot',
    '*.gif',
    '*.ico',
    '*.jpeg',
    '*.jpg',
    '*.mo',
    '*.mp3',
    '*.otf',
    '*.pdf',
    '*.png',
    '*.ttf',
    '*.woff',
    '*.woff2',
    '*.xls',
    '*.xlsx',
)
"""
A tuple of strings with :mod:`fnmatch` patterns of common file types to be
ignored by :func:`find_object_files()` even if the files in question have the
executable bit set and contain binary data.

This option was added to minimize harmless but possibly confusing warnings from
:func:`strip_object_files()` and/or :func:`find_system_dependencies()` caused
by binary files that happen to (incorrectly) have their executable bit set.
"""

ALLOW_CHOWN = coerce_boolean(os.environ.get('DPT_CHOWN_FILES', 'true'))
"""
:data:`True` to allow :func:`build_package()` to normalize file ownership by
running :man:`chown`, :data:`False` to disallow usage of :man:`chown`.

The environment variable ``$DPT_CHOWN_FILES`` can be used to control the value
of this variable (see :func:`~humanfriendly.coerce_boolean()` for acceptable
values).
"""

ALLOW_FAKEROOT_OR_SUDO = coerce_boolean(os.environ.get('DPT_ALLOW_FAKEROOT_OR_SUDO', 'true'))
"""
:data:`True` to allow :func:`build_package()` to use :man:`fakeroot` (when
available) or :man:`sudo` (when :man:`fakeroot` is not available),
:data:`False` to disallow this behavior.

The environment variable ``$DPT_ALLOW_FAKEROOT_OR_SUDO`` can be used to control
the value of this variable (see :func:`~humanfriendly.coerce_boolean()` for
acceptable values).
"""

ALLOW_HARD_LINKS = coerce_boolean(os.environ.get('DPT_HARD_LINKS', 'true'))
"""
:data:`True` to allow :func:`copy_package_files()` to use hard links to
optimize file copying, :data:`False` to disallow this behavior.

The environment variable ``$DPT_HARD_LINKS`` can be used to control the value
of this variable (see :func:`~humanfriendly.coerce_boolean()` for acceptable
values).
"""

ALLOW_RESET_SETGID = coerce_boolean(os.environ.get('DPT_RESET_SETGID', 'true'))
"""
:data:`True` to allow :func:`build_package()` to remove the sticky bit from
directories, :data:`False` to disallow this behavior.

The environment variable ``$DPT_RESET_SETGID`` can be used to control the value
of this variable (see :func:`~humanfriendly.coerce_boolean()` for acceptable
values).
"""

PARSE_STRICT = coerce_boolean(os.environ.get('DPT_PARSE_STRICT', 'true'))
"""
If :data:`PARSE_STRICT` is :data:`True` then :func:`parse_filename()` expects
filenames of ``*.deb`` archives to encode the package name, version and
architecture delimited by underscores. This is the default behavior and
backwards compatible with deb-pkg-tools 6.0 and older.

If :data:`PARSE_STRICT` is :data:`False` then :func:`parse_filename()` will
fall back to reading the package name, version and architecture from the
metadata contained in the ``*.deb`` archive.

The environment variable ``$DPT_PARSE_STRICT`` can be used to control the value
of this variable (see :func:`~humanfriendly.coerce_boolean()` for acceptable
values).
"""

ROOT_USER = os.environ.get('DPT_ROOT_USER', 'root')
"""
The name of the system user that is used by :func:`build_package()` when it
normalizes file ownership using :man:`chown` (controlled by
:data:`ALLOW_CHOWN`).

The environment variable ``$DPT_ROOT_USER`` can be used to control the value
of this variable.
"""

ROOT_GROUP = os.environ.get('DPT_ROOT_GROUP', 'root')
"""
The name of the system group that is used by :func:`build_package()` when it
normalizes file ownership using :man:`chown` (controlled by
:data:`ALLOW_CHOWN`).

The environment variable ``$DPT_ROOT_GROUP`` can be used to control the value
of this variable.
"""


def parse_filename(filename, cache=None):
    """
    Parse the filename of a Debian binary package archive.

    :param filename: The pathname of a Debian binary package archive (a string).
    :param cache: The :class:`.PackageCache` to use when :data:`PARSE_STRICT`
                  is :data:`False` (defaults to :data:`None`).
    :returns: A :class:`PackageFile` object.
    :raises: :exc:`~exceptions.ValueError` in the following circumstances:

             - The filename extension doesn't match any of the known
               :data:`BINARY_PACKAGE_ARCHIVE_EXTENSIONS`.

             - The filename doesn't have three underscore separated components
               (and :data:`PARSE_STRICT` is :data:`True`).

    This function parses the filename of a Debian binary package archive into
    three fields: the name of the package, its version and its architecture.
    See also :func:`determine_package_archive()`.

    Here's an example:

    >>> from deb_pkg_tools.package import parse_filename
    >>> components = parse_filename('/var/cache/apt/archives/python2.7_2.7.3-0ubuntu3.4_amd64.deb')
    >>> print(repr(components))
    PackageFile(name='python2.7',
                version='2.7.3-0ubuntu3.4',
                architecture='amd64',
                filename='/var/cache/apt/archives/python2.7_2.7.3-0ubuntu3.4_amd64.deb')

    """
    if isinstance(filename, PackageFile):
        return filename
    pathname = os.path.abspath(filename)
    filename = os.path.basename(pathname)
    basename, extension = os.path.splitext(filename)
    if extension not in BINARY_PACKAGE_ARCHIVE_EXTENSIONS:
        raise ValueError("Refusing to parse filename with unknown extension! (%r)" % pathname)
    components = basename.split('_')
    if len(components) == 3:
        return PackageFile(
            name=components[0],
            version=Version(components[1]),
            architecture=components[2],
            filename=pathname,
        )
    elif not PARSE_STRICT and os.path.isfile(pathname):
        control_fields = inspect_package_fields(pathname, cache)
        return PackageFile(
            name=control_fields['Package'],
            version=Version(control_fields['Version']),
            architecture=control_fields.get('Architecture', ''),
            filename=pathname,
        )
    else:
        # Up to deb-pkg-tools 6.0 strict mode was the only supported behavior.
        # For now it remains as the default behavior because of backwards
        # compatibility concerns / the principle of least surprise.
        msg = "Filename doesn't have three underscore separated components! (%r)"
        raise ValueError(msg % pathname)


class PackageFile(collections.namedtuple('PackageFile', 'name, version, architecture, filename')):

    """
    A named tuple with the result of :func:`parse_filename()`.

    The function :func:`parse_filename()` reports the fields of a package
    archive's filename as a :class:`PackageFile` object (a named tuple).
    Here are the fields supported by these named tuples:

    .. attribute:: name

       The name of the package (a string).

    .. attribute:: version

       The version of the package (a :class:`.Version` object).

    .. attribute:: architecture

       The architecture of the package (a string).

    .. attribute:: filename

       The absolute pathname of the package archive (a string).

    The values of the :attr:`directory`, :attr:`other_versions` and
    :attr:`newer_versions` properties are generated on demand.

    :class:`PackageFile` objects support sorting according to Debian's
    package version comparison algorithm as implemented in ``dpkg
    --compare-versions``.
    """

    @property
    def directory(self):
        """The absolute pathname of the directory containing the package archive (a string)."""
        return os.path.dirname(self.filename)

    @property
    def other_versions(self):
        """A list of :class:`PackageFile` objects with other versions of the same package in the same directory."""
        archives = []
        # TODO Inject cache given to parse_filename() by converting PackageFile
        # from a named tuple to PropertyManager with key properties for the
        # name, version and architecture fields? We'd lose indexing which means
        # dropping backwards compatibility. All of this to avoid an edge case
        # that could theoretically become a performance issue :-|.
        for other_archive in find_package_archives(self.directory):
            if self.name == other_archive.name and self.version != other_archive.version:
                archives.append(other_archive)
        return archives

    @property
    def newer_versions(self):
        """A list of :class:`PackageFile` objects with newer versions of the same package in the same directory."""
        archives = []
        for other_archive in self.other_versions:
            if other_archive.version > self.version:
                archives.append(other_archive)
        return archives


def find_package_archives(directory, cache=None):
    """
    Find the Debian package archive(s) in the given directory.

    :param directory: The pathname of a directory (a string).
    :param cache: The :class:`.PackageCache` that :func:`parse_filename()`
                  should use when :data:`PARSE_STRICT` is :data:`False`
                  (defaults to :data:`None`).
    :returns: A list of :class:`PackageFile` objects.
    """
    archives = []
    for entry in os.listdir(directory):
        if entry.endswith(BINARY_PACKAGE_ARCHIVE_EXTENSIONS):
            pathname = os.path.join(directory, entry)
            if os.path.isfile(pathname):
                archives.append(parse_filename(pathname, cache))
    return archives


def collect_related_packages(filename, strict=None, cache=None, interactive=None):
    """
    Collect the package archive(s) related to the given package archive.

    :param filename: The filename of an existing ``*.deb`` archive (a string).
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :param interactive: :data:`True` to draw an interactive spinner on the
                        terminal (see :class:`~humanfriendly.terminal.spinners.Spinner`),
                        :data:`False` to skip the interactive spinner or
                        :data:`None` to detect whether we're connected to an
                        interactive terminal.
    :returns: A list of :class:`PackageFile` objects.

    This works by parsing and resolving the dependencies of the given package
    to filenames of package archives, then parsing and resolving the
    dependencies of those package archives, etc. until no more relationships
    can be resolved to existing package archives.

    Known limitations / sharp edges of this function:

    - Only `Depends` and `Pre-Depends` relationships are processed, `Provides`
      is ignored. I'm not yet sure whether it makes sense to add support for
      `Conflicts`, `Provides` and `Replaces` (and how to implement it).

    - Unsatisfied relationships don't trigger a warning or error because this
      function doesn't know in what context a package can be installed (e.g.
      which additional repositories a given apt client has access to).

    - Please thoroughly test this functionality before you start to rely on it.
      What this function tries to do is a complex operation to do correctly
      (given the limited information this function has to work with) and the
      implementation is far from perfect. Bugs have been found and fixed in
      this code and more bugs will undoubtedly be discovered. You've been
      warned :-).

    - This function can be rather slow on large package repositories and
      dependency sets due to the incremental nature of the related package
      collection. It's a known issue / limitation.

    This function is used to implement the ``deb-pkg-tools --collect`` command:

    .. code-block:: sh

       $ deb-pkg-tools -c /tmp python-deb-pkg-tools_1.13-1_all.deb
       2014-05-18 08:33:42 deb_pkg_tools.package INFO Collecting packages related to ~/python-deb-pkg-tools_1.13-1_all.deb ..
       2014-05-18 08:33:42 deb_pkg_tools.package INFO Scanning ~/python-deb-pkg-tools_1.13-1_all.deb ..
       2014-05-18 08:33:42 deb_pkg_tools.package INFO Scanning ~/python-coloredlogs_0.4.8-1_all.deb ..
       2014-05-18 08:33:42 deb_pkg_tools.package INFO Scanning ~/python-chardet_2.2.1-1_all.deb ..
       2014-05-18 08:33:42 deb_pkg_tools.package INFO Scanning ~/python-humanfriendly_1.7.1-1_all.deb ..
       2014-05-18 08:33:42 deb_pkg_tools.package INFO Scanning ~/python-debian_0.1.21-1_all.deb ..
       Found 5 package archives:
        - ~/python-chardet_2.2.1-1_all.deb
        - ~/python-coloredlogs_0.4.8-1_all.deb
        - ~/python-deb-pkg-tools_1.13-1_all.deb
        - ~/python-humanfriendly_1.7.1-1_all.deb
        - ~/python-debian_0.1.21-1_all.deb
       Copy 5 package archives to /tmp? [Y/n] y
       2014-05-18 08:33:44 deb_pkg_tools.cli INFO Done! Copied 5 package archives to /tmp.
    """
    given_archive = parse_filename(filename, cache)
    logger.info("Collecting packages related to %s ..", format_path(given_archive.filename))
    # Group the related package archive candidates by name.
    candidate_archives = collections.defaultdict(list)
    for archive in find_package_archives(given_archive.directory, cache):
        if archive.name != given_archive.name:
            candidate_archives[archive.name].append(archive)
    # Sort the related package archive candidates by descending versions
    # because we want to prefer newer versions over older versions.
    for name in candidate_archives:
        candidate_archives[name].sort(reverse=True)
    # Prepare for more than one attempt to find a converging set of related
    # package archives so we can properly deal with conflicts between
    # transitive (indirect) dependencies.
    while True:
        try:
            # Assuming there are no possible conflicts one call will be enough.
            return collect_related_packages_helper(candidate_archives, given_archive, cache, interactive)
        except CollectedPackagesConflict as e:
            # If we do encounter conflicts we take the brute force approach of
            # removing the conflicting package archive(s) from the set of
            # related package archive candidates and retrying from scratch.
            # This approach works acceptably as long as your repository isn't
            # full of conflicts between transitive dependencies...
            logger.warning("Removing %s from candidates (%s) ..",
                           pluralize(len(e.conflicts), "conflicting archive"),
                           concatenate(os.path.basename(archive.filename) for archive in e.conflicts))
            for archive in e.conflicts:
                candidate_archives[archive.name].remove(archive)
            logger.info("Retrying related archive collection without %s ..",
                        pluralize(len(e.conflicts), "conflicting archive"))


def collect_related_packages_helper(candidate_archives, given_archive, cache, interactive):
    """Internal helper for package collection to enable simple conflict resolution."""
    # Enable mutation of the candidate archives data structure inside the scope
    # of this function without mutating the original data structure.
    candidate_archives = copy.deepcopy(candidate_archives)
    # Prepare some internal state.
    archives_to_scan = [given_archive]
    collected_archives = []
    relationship_sets = set()
    # Render an interactive spinner as a simple means of feedback to the operator.
    with Spinner(label="Collecting related packages", interactive=interactive, timer=Timer()) as spinner:
        # Loop to collect the related packages.
        while archives_to_scan:
            selected_archive = archives_to_scan.pop(0)
            logger.debug("Scanning %s ..", format_path(selected_archive.filename))
            # Find the relationships of the given package.
            control_fields = inspect_package_fields(selected_archive.filename, cache)
            for field_name in DEPENDENCY_FIELDS:
                if field_name in control_fields:
                    relationship_sets.add(control_fields[field_name])
            # For each group of package archives sharing the same package name ..
            for package_name in sorted(candidate_archives):
                # For each version of the package ..
                for package_archive in list(candidate_archives[package_name]):
                    package_matches = match_relationships(package_archive, relationship_sets)
                    spinner.step()
                    if package_matches is True:
                        logger.debug("Package archive matched all relationships: %s", package_archive.filename)
                        # Move the selected version of the package archive from the
                        # candidates to the list of selected package archives.
                        collected_archives.append(package_archive)
                        # Prepare to scan and collect dependencies of the selected
                        # package archive in a future iteration of the outermost
                        # (while) loop.
                        archives_to_scan.append(package_archive)
                        # Ignore all other versions of the package inside this call
                        # to collect_related_packages_helper().
                        candidate_archives.pop(package_name)
                        # Break out of the loop to avoid scanning other versions of
                        # this package archive; we've made our choice now.
                        break
                    elif package_matches is False:
                        # If we're sure we can exclude this version of the package
                        # from future iterations it could be worth it to speed up
                        # the process on big repositories / dependency sets.
                        candidate_archives[package_name].remove(package_archive)
                        # Keep looking for a match in another version.
                    elif package_matches is None:
                        # Break out of the loop that scans multiple versions of the
                        # same package because none of the relationship sets collected
                        # so far reference the name of this package (this is intended
                        # as a harmless optimization).
                        break
    # Check for conflicts in the collected set of related package archives.
    conflicts = [a for a in collected_archives if not match_relationships(a, relationship_sets)]
    if conflicts:
        raise CollectedPackagesConflict(conflicts)
    else:
        return collected_archives


def match_relationships(package_archive, relationship_sets):
    """
    Internal helper for package collection to validate that all relationships are satisfied.

    This function enables :func:`collect_related_packages_helper()` to validate
    that all relationships are satisfied while the set of related package
    archives is being collected and again afterwards to make sure that no
    previously drawn conclusions were invalidated by additionally collected
    package archives.
    """
    archive_matches = None
    for relationships in relationship_sets:
        status = relationships.matches(package_archive.name, package_archive.version)
        if status is True and archive_matches is not False:
            archive_matches = True
        elif status is False:
            # This package archive specifically conflicts with (at least) one
            # of the given relationship sets.
            archive_matches = False
            # Short circuit the evaluation of further relationship sets because
            # we've already found our answer.
            break
    return archive_matches


class CollectedPackagesConflict(Exception):

    """Exception raised by :func:`collect_related_packages_helper()`."""

    def __init__(self, conflicts):
        """
        Construct a :exc:`CollectedPackagesConflict` exception.

        :param conflicts: A list of conflicting :class:`PackageFile` objects.
        """
        self.conflicts = conflicts


def find_latest_version(packages, cache=None):
    """
    Find the package archive with the highest version number.

    :param packages: A list of filenames (strings) and/or
                     :class:`PackageFile` objects.
    :param cache: The :class:`.PackageCache` that :func:`parse_filename()`
                  should use when :data:`PARSE_STRICT` is :data:`False`
                  (defaults to :data:`None`).
    :returns: The :class:`PackageFile` with the highest version number.
    :raises: :exc:`~exceptions.ValueError` when not all of the given package
             archives share the same package name.

    This function uses :class:`.Version` objects for version comparison.
    """
    packages = sorted(parse_filename(fn, cache) for fn in packages)
    names = set(p.name for p in packages)
    if len(names) > 1:
        msg = "Refusing to compare unrelated packages! (%s)"
        raise ValueError(msg % concatenate(sorted(names)))
    return packages[-1]


def group_by_latest_versions(packages, cache=None):
    """
    Group package archives by name of package and find latest version of each.

    :param packages: A list of filenames (strings) and/or
                     :class:`PackageFile` objects.
    :param cache: The :class:`.PackageCache` that :func:`parse_filename()`
                  should use when :data:`PARSE_STRICT` is :data:`False`
                  (defaults to :data:`None`).
    :returns: A dictionary with package names as keys and
              :class:`PackageFile` objects as values.
    """
    grouped_packages = collections.defaultdict(set)
    for value in packages:
        package = parse_filename(value, cache)
        grouped_packages[package.name].add(package)
    return dict((n, find_latest_version(p, cache)) for n, p in grouped_packages.items())


def inspect_package(archive, cache=None):
    """
    Get the metadata and contents from a ``*.deb`` archive.

    :param archive: The pathname of an existing ``*.deb`` archive.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :returns: A tuple with two dictionaries:

              1. The result of :func:`inspect_package_fields()`.
              2. The result of :func:`inspect_package_contents()`.
    """
    return (inspect_package_fields(archive, cache),
            inspect_package_contents(archive, cache))


def inspect_package_fields(archive, cache=None):
    r"""
    Get the fields (metadata) from a ``*.deb`` archive.

    :param archive: The pathname of an existing ``*.deb`` archive.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :returns: A dictionary with control file fields (the result of
              :func:`.parse_control_fields()`).

    Here's an example:

    >>> from deb_pkg_tools.package import inspect_package_fields
    >>> print(repr(inspect_package_fields('python3.4-minimal_3.4.0-1+precise1_amd64.deb')))
    {'Architecture': u'amd64',
     'Conflicts': RelationshipSet(VersionedRelationship(name=u'binfmt-support', operator=u'<<', version=u'1.1.2')),
     'Depends': RelationshipSet(VersionedRelationship(name=u'libpython3.4-minimal', operator=u'=', version=u'3.4.0-1+precise1'),
                                VersionedRelationship(name=u'libexpat1', operator=u'>=', version=u'1.95.8'),
                                VersionedRelationship(name=u'libgcc1', operator=u'>=', version=u'1:4.1.1'),
                                VersionedRelationship(name=u'zlib1g', operator=u'>=', version=u'1:1.2.0')),
     'Description': u'Minimal subset of the Python language (version 3.4)\n This package contains the interpreter and some essential modules.  It can\n be used in the boot process for some basic tasks.\n See /usr/share/doc/python3.4-minimal/README.Debian for a list of the modules\n contained in this package.',
     'Installed-Size': 3586,
     'Maintainer': u'Felix Krull <f_krull@gmx.de>',
     'Multi-Arch': u'allowed',
     'Original-Maintainer': u'Matthias Klose <doko@debian.org>',
     'Package': u'python3.4-minimal',
     'Pre-Depends': RelationshipSet(VersionedRelationship(name=u'libc6', operator=u'>=', version=u'2.15')),
     'Priority': u'optional',
     'Recommends': u'python3.4',
     'Section': u'python',
     'Source': u'python3.4',
     'Suggests': RelationshipSet(Relationship(name=u'binfmt-support')),
     'Version': u'3.4.0-1+precise1'}

    """
    if cache:
        entry = cache.get_entry('control-fields', archive)
        value = entry.get_value()
        if value is not None:
            return value
    listing = execute('dpkg-deb', '-f', archive, logger=logger, capture=True)
    fields = parse_control_fields(parse_deb822(listing, filename=archive))
    if cache:
        entry.set_value(fields)
    return fields


def inspect_package_contents(archive, cache=None):
    """
    Get the contents from a ``*.deb`` archive.

    :param archive: The pathname of an existing ``*.deb`` archive.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :returns: A dictionary with the directories and files contained in the
              package. The dictionary keys are the absolute pathnames and the
              dictionary values are :class:`ArchiveEntry` objects (see the
              example below).

    An example:

    >>> from deb_pkg_tools.package import inspect_package_contents
    >>> print(repr(inspect_package_contents('python3.4-minimal_3.4.0-1+precise1_amd64.deb')))
    {u'/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:54', target=u''),
     u'/usr/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:52', target=u''),
     u'/usr/bin/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:54', target=u''),
     u'/usr/bin/python3.4': ArchiveEntry(permissions=u'-rwxr-xr-x', owner=u'root', group=u'root', size=3536680, modified=u'2014-03-20 23:54', target=u''),
     u'/usr/bin/python3.4m': ArchiveEntry(permissions=u'hrwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:54', target=u'/usr/bin/python3.4'),
     u'/usr/share/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:53', target=u''),
     u'/usr/share/binfmts/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:53', target=u''),
     u'/usr/share/binfmts/python3.4': ArchiveEntry(permissions=u'-rw-r--r--', owner=u'root', group=u'root', size=72, modified=u'2014-03-20 23:53', target=u''),
     u'/usr/share/doc/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:53', target=u''),
     u'/usr/share/doc/python3.4-minimal/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:54', target=u''),
     u'/usr/share/doc/python3.4-minimal/README.Debian': ArchiveEntry(permissions=u'-rw-r--r--', owner=u'root', group=u'root', size=3779, modified=u'2014-03-20 23:52', target=u''),
     u'/usr/share/doc/python3.4-minimal/changelog.Debian.gz': ArchiveEntry(permissions=u'-rw-r--r--', owner=u'root', group=u'root', size=28528, modified=u'2014-03-20 22:32', target=u''),
     u'/usr/share/doc/python3.4-minimal/copyright': ArchiveEntry(permissions=u'-rw-r--r--', owner=u'root', group=u'root', size=51835, modified=u'2014-03-20 20:37', target=u''),
     u'/usr/share/man/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:52', target=u''),
     u'/usr/share/man/man1/': ArchiveEntry(permissions=u'drwxr-xr-x', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:54', target=u''),
     u'/usr/share/man/man1/python3.4.1.gz': ArchiveEntry(permissions=u'-rw-r--r--', owner=u'root', group=u'root', size=5340, modified=u'2014-03-20 23:30', target=u''),
     u'/usr/share/man/man1/python3.4m.1.gz': ArchiveEntry(permissions=u'lrwxrwxrwx', owner=u'root', group=u'root', size=0, modified=u'2014-03-20 23:54', target=u'python3.4.1.gz')}

    """
    if cache:
        entry = cache.get_entry('contents', archive)
        value = entry.get_value()
        if value is not None:
            return value
    contents = {}
    for line in execute('dpkg-deb', '-c', archive, logger=logger, capture=True).splitlines():
        # Example output of dpkg-deb -c archive.deb:
        # drwxr-xr-x root/root 0 2013-07-08 17:49 ./usr/share/doc/
        # lrwxrwxrwx root/root 0 2013-09-26 22:29 ./usr/bin/pdb2.7 -> ../lib/python2.7/pdb.py
        fields = line.split(None, 5)
        permissions = fields[0]
        owner, _, group = fields[1].partition('/')
        # The third field (index 2) is normally the file size, but for device
        # files it gives the comma separated device type major / minor numbers.
        # More details: https://github.com/xolox/python-deb-pkg-tools/pull/22
        if fields[2].isdigit():
            device_type = 0, 0
            size = int(fields[2])
        else:
            major_nr, _, minor_nr = fields[2].partition(',')
            device_type = int(major_nr), int(minor_nr)
            size = 0
        modified = fields[3] + ' ' + fields[4]
        pathname = re.sub('^./', '/', fields[5])
        pathname, _, target = pathname.partition(' -> ')
        if not target:
            pathname, _, target = pathname.partition(' link to ')
            target = re.sub('^./', '/', target)
        contents[pathname] = ArchiveEntry(permissions, owner, group, size, modified, target, device_type)
    if cache:
        entry.set_value(contents)
    return contents


class ArchiveEntry(collections.namedtuple('ArchiveEntry', 'permissions, owner, group, size, modified, target, device_type')):

    """
    A named tuple with the result of :func:`inspect_package()`.

    The function :func:`inspect_package()` reports the contents of package
    archives as a dictionary containing named tuples. Here are the fields
    supported by those named tuples:

    .. attribute:: permissions

       The entry type and permission bits just like ``ls -l`` prints them (a string like `drwxr-xr-x`).

    .. attribute:: owner

       The username of the owner of the entry (a string).

    .. attribute:: group

       The group name of group owning the entry (a string).

    .. attribute:: size

       The size of the entry in bytes (an integer).

    .. attribute:: modified

       A string like ``2013-09-26 22:28``.

    .. attribute:: target

       If the entry represents a symbolic link this field gives the pathname of
       the target of the symbolic link. Defaults to an empty string.

    .. attribute:: device_type

       If the entry represents a device file this field gives the device type
       major and minor numbers as a tuple of two integers. Defaults to a tuple
       with two zeros.

       .. note:: This defaults to a tuple with two zeros so that
                 :class:`ArchiveEntry` tuples can be reliably sorted just like
                 regular tuples (i.e. without getting
                 :exc:`~exceptions.TypeError` exceptions due to comparisons
                 between incompatible value types).
    """


def build_package(directory, repository=None, check_package=True, copy_files=True, **options):
    """
    Create a Debian package using the ``dpkg-deb --build`` command.

    :param directory: The pathname of a directory tree suitable for packaging
                      with ``dpkg-deb --build``.
    :param repository: The pathname of the directory where the generated
                       ``*.deb`` archive should be stored.

                       By default a temporary directory is created to store the
                       generated archive, in this case the caller is
                       responsible for cleaning up the directory.

                       Before deb-pkg-tools 2.0 this defaulted to the system
                       wide temporary directory which could result in corrupted
                       archives during concurrent builds.
    :param check_package: If :data:`True` (the default) Lintian_ is run to check
                          the resulting package archive for possible issues.
    :param copy_files: If :data:`True` (the default) the package's files are copied
                       to a temporary directory before being modified. You can
                       set this to :data:`False` if you're already working on a
                       copy and don't want yet another copy to be made.
    :param update_conffiles: If :data:`True` (the default) files in ``/etc``
                             will be added to ``DEBIAN/conffiles``
                             automatically using :func:`update_conffiles()`,
                             otherwise it is up to the caller whether to do
                             this or not.
    :param strip_object_files: If :data:`True` (not the default) then
                               :func:`strip_object_files()` will be used.
    :param find_system_dependencies: If :data:`True` (not the default) then
                                     :func:`find_system_dependencies()` will be
                                     used.
    :returns: The pathname of the generated ``*.deb`` archive.
    :raises: :exc:`executor.ExternalCommandFailed` if any of the external
             commands invoked by this function fail.

    The ``dpkg-deb --build`` command requires a certain directory tree layout
    and specific files; for more information about this topic please refer to
    the `Debian Binary Package Building HOWTO`_. The :func:`build_package()`
    function performs the following steps to build a package:

    1. Copies the files in the source directory to a temporary build directory.
    2. Updates the Installed-Size_ field in the ``DEBIAN/control`` file
       based on the size of the given directory (using
       :func:`update_installed_size()`).
    3. Sets the owner and group of all files to ``root`` because this is the
       only user account guaranteed to always be available. This uses the
       :man:`fakeroot` command so you don't actually need ``root`` access to
       use :func:`build_package()`.
    4. Runs the command ``fakeroot dpkg-deb --build`` to generate a Debian
       package from the files in the build directory.
    5. Runs Lintian_ to check the resulting package archive for possible
       issues. The result of Lintian is purely informational: If 'errors' are
       reported and Lintian exits with a nonzero status code, this is ignored
       by :func:`build_package()`.

    .. _Debian Binary Package Building HOWTO: http://tldp.org/HOWTO/html_single/Debian-Binary-Package-Building-HOWTO/
    .. _Installed-Size: http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Installed-Size
    .. _Lintian: http://lintian.debian.org/
    """
    if not repository:
        repository = tempfile.mkdtemp(prefix='deb-pkg-tools-build-')
    package_file = os.path.join(repository, determine_package_archive(directory))
    logger.debug("Preparing to build package: %s", format_path(package_file))
    try:
        if copy_files:
            build_directory = tempfile.mkdtemp()
            logger.debug("Created build directory: %s", format_path(build_directory))
            # This no longer uses hard links because of all the file permission
            # magic going on further down in this function (permissions are
            # shared between all hard links pointing to an inode).
            copy_package_files(directory, build_directory, hard_links=False)
        else:
            build_directory = directory
        control_file = os.path.join(build_directory, 'DEBIAN', 'control')
        clean_package_tree(build_directory)
        # Automatically mark configuration files?
        if options.get('update_conffiles', True):
            update_conffiles(build_directory)
        # Process binary executables and *.so files?
        if any(map(options.get, ('find_system_dependencies', 'strip_object_files'))):
            object_files = find_object_files(build_directory)
        if options.get('find_system_dependencies', False) and object_files:
            system_dependencies = find_system_dependencies(object_files)
            patch_control_file(control_file, {'Depends': system_dependencies})
        if options.get('strip_object_files', False) and object_files:
            strip_object_files(object_files)
        # Calculate installed size after (potentially) stripping object files.
        update_installed_size(build_directory)
        # Sanitize the permission bits of the root directory. Most build
        # directories will have been created with tempfile.mkdtemp() which
        # creates the directory with mode 0700. The Debian packaging system
        # really doesn't care about any of this, but:
        #
        #  1. It looks weird in the output of ``deb-pkg-tools -i`` :-)
        #  2. When you convert a ``*.deb`` to ``*.rpm`` with Alien and install
        #     the RPM the 0700 mode is actually applied to the system where you
        #     install the package. As you can imagine, the results are
        #     disastrous...
        os.chmod(build_directory, 0o755)
        if ALLOW_CHOWN:
            # Make sure all files included in the package are owned by `root'
            # (the only account guaranteed to exist on all systems).
            user_spec = '%s:%s' % (ROOT_USER, ROOT_GROUP)
            logger.debug("Resetting file ownership (to %s) ..", user_spec)
            execute('chown', '-R', user_spec, build_directory,
                    fakeroot=ALLOW_FAKEROOT_OR_SUDO, logger=logger)
        # Reset the file modes of pre/post installation/removal scripts.
        for script_name in ('preinst', 'postinst', 'prerm', 'postrm'):
            script_path = os.path.join(build_directory, 'DEBIAN', script_name)
            if os.path.isfile(script_path):
                logger.debug("Resetting file modes (%s to 755) ..", script_path)
                os.chmod(script_path, 0o755)
        # System packages generally install files that are read only and
        # readable (and possibly executable) for everyone (owner, group and
        # world) so we'll go ahead and remove some potentially harmful
        # permission bits (harmful enough that Lintian complains about them).
        logger.debug("Resetting file modes (go-w) ..")
        execute('chmod', '-R', 'go-w', build_directory,
                fakeroot=ALLOW_FAKEROOT_OR_SUDO, logger=logger)
        # Remove the setgid bit from all directories in the package. Rationale:
        # In my situation package templates are stored in a directory where a
        # team of people have push access (I imagine that this is a common
        # setup). To facilitate shared push access a shared primary UNIX group
        # is used with the sticky bit on directories. However dpkg-deb *really*
        # doesn't like this, failing with the error "dpkg-deb: control
        # directory has bad permissions 2755 (must be >=0755 and <=0775)".
        if ALLOW_RESET_SETGID:
            logger.debug("Removing sticky bit from directories (g-s) ..")
            execute('find -type d -print0 | xargs -0 chmod g-s',
                    directory=build_directory,
                    fakeroot=ALLOW_FAKEROOT_OR_SUDO, logger=logger)
        # Make sure files in /etc/sudoers.d have the correct permissions.
        sudoers_directory = os.path.join(build_directory, 'etc', 'sudoers.d')
        if os.path.isdir(sudoers_directory):
            for filename in os.listdir(sudoers_directory):
                pathname = os.path.join(sudoers_directory, filename)
                logger.debug("Resetting file modes (%s to 440) ..", pathname)
                os.chmod(pathname, 0o440)
        # Build the package using `dpkg-deb'.
        logger.info("Building package in %s ..", format_path(build_directory))
        execute('dpkg-deb', '--build', build_directory, package_file,
                fakeroot=ALLOW_FAKEROOT_OR_SUDO, logger=logger)
        # Check the package for possible issues using Lintian?
        if check_package:
            if not os.access('/usr/bin/lintian', os.X_OK):
                logger.warning("Lintian is not installed, skipping sanity check.")
            else:
                logger.info("Checking package for issues using Lintian ..")
                lintian_command = ['lintian']
                if os.getuid() == 0:
                    lintian_command.append('--allow-root')
                lintian_command.append('--color=auto')
                lintian_command.append(package_file)
                execute(*lintian_command, logger=logger, check=False)
        return package_file
    finally:
        if copy_files:
            logger.debug("Removing build directory: %s", format_path(build_directory))
            shutil.rmtree(build_directory)


def determine_package_archive(directory):
    """
    Determine the name of a package archive before building it.

    :param source_directory: The pathname of a directory tree suitable for
                             packaging with ``dpkg-deb --build``.
    :returns: The filename of the ``*.deb`` archive to be built.

    This function determines the name of the ``*.deb`` package archive that
    will be generated from a directory tree suitable for packaging with
    ``dpkg-deb --build``. See also :func:`parse_filename()`.
    """
    control_file = os.path.join(directory, 'DEBIAN', 'control')
    with open(control_file) as handle:
        fields = parse_deb822(handle.read(), filename=control_file)
    components = [fields['Package'], fields['Version']]
    architecture = fields.get('Architecture', '').strip()
    if architecture:
        components.append(architecture)
    return '%s.deb' % '_'.join(components)


def copy_package_files(from_directory, to_directory, hard_links=True):
    """
    Copy package files to a temporary directory, using hard links when possible.

    :param from_directory: The pathname of a directory tree suitable for
                           packaging with ``dpkg-deb --build``.
    :param to_directory: The pathname of a temporary build directory.
    :param hard_links: Use hard links to speed up copying when possible.

    This function copies a directory tree suitable for packaging with
    ``dpkg-deb --build`` to a temporary build directory so that individual
    files can be replaced without changing the original directory tree. If the
    build directory is on the same file system as the source directory, hard
    links are used to speed up the copy. This function is used by
    :func:`build_package()`.
    """
    logger.info("Copying files (%s) to temporary directory (%s) ..",
                format_path(from_directory), format_path(to_directory))
    command = ['cp', '-a']
    makedirs(to_directory)
    if hard_links and ALLOW_HARD_LINKS:
        # Check whether we can use hard links to speed up the copy. In the past
        # this used the following simple and obvious check:
        #
        #   os.stat(source_directory).st_dev == os.stat(build_directory).st_dev
        #
        # However this expression holds true inside schroot, yet `cp -al' fails
        # when trying to create the hard links! This is why the following code now
        # tries to create an actual hard link to verify that `cp -al' can be used.
        test_file_from = None
        test_file_to = None
        try:
            # Find a unique filename that we can create and destroy without
            # touching any of the caller's files.
            while True:
                test_name = 'deb-pkg-tools-hard-link-test-%d' % random.randint(1, 1000)
                test_file_from = os.path.join(from_directory, test_name)
                test_file_to = os.path.join(to_directory, test_name)
                if not os.path.isfile(test_file_from):
                    break
            # Create the test file.
            with open(test_file_from, 'w') as handle:
                handle.write('test')
            os.link(test_file_from, test_file_to)
            logger.debug("Speeding up file copy using hard links ..")
            command.append('-l')
        except (IOError, OSError):
            pass
        finally:
            for test_file in [test_file_from, test_file_to]:
                if test_file and os.path.isfile(test_file):
                    os.unlink(test_file)
    # I know this looks really funky, but this is a valid use of shell escaping
    # and globbing (obviously I tested it ;-).
    command.append('%s/*' % pipes.quote(from_directory))
    command.append(pipes.quote(to_directory))
    execute(' '.join(command), logger=logger)


def clean_package_tree(directory, remove_dirs=DIRECTORIES_TO_REMOVE, remove_files=FILES_TO_REMOVE):
    """
    Clean up files that should not be included in a Debian package from the given directory.

    :param directory: The pathname of the directory to clean (a string).
    :param remove_dirs: An iterable with filename patterns of directories that
                        should not be included in the package. Defaults to
                        :data:`DIRECTORIES_TO_REMOVE`.
    :param remove_files: An iterable with filename patterns of files that
                         should not be included in the package. Defaults to
                         :data:`FILES_TO_REMOVE`.

    Uses the :mod:`fnmatch` module for directory and filename matching.
    Matching is done on the base name of each directory and file. This function
    assumes it is safe to unlink files from the given directory (which it
    should be when :func:`copy_package_files()` was previously called, e.g. by
    :func:`build_package()`).
    """
    for root, dirs, files in os.walk(directory):
        for name in dirs:
            if any(fnmatch.fnmatch(name, p) for p in remove_dirs):
                pathname = os.path.join(root, name)
                logger.debug("Cleaning up directory: %s", format_path(pathname))
                shutil.rmtree(pathname)
        for name in files:
            if any(fnmatch.fnmatch(name, p) for p in remove_files):
                pathname = os.path.join(root, name)
                logger.debug("Cleaning up file: %s", format_path(pathname))
                os.unlink(pathname)


def strip_object_files(object_files):
    """
    Use :man:`strip` to make object files smaller.

    :param object_files: An iterable of strings with filenames of object files.

    This function runs ``strip --strip-unneeded`` on each of the given object
    files to make them as small as possible. To find the object files you can
    use :func:`find_object_files()`.

    If the :man:`strip` program is not installed a `debug` message is logged
    but no exceptions are raised. When the :man:`strip` program fails a
    `warning` message is logged but again, no exceptions are raised.

    One reason not to propagate these error conditions as exceptions is that
    :func:`find_object_files()` will match files with binary contents that
    have their executable bit set, regardless of whether those files are
    actually valid object files.
    """
    for filename in object_files:
        try:
            execute('strip', '--strip-unneeded', filename, logger=logger, silent=True)
        except CommandNotFound:
            # Don't bother trying to strip any more object files.
            logger.debug("Not stripping object files because 'strip' program isn't installed.")
            break
        except ExternalCommandFailed as e:
            logger.warning("Failed to strip object file: %s", e)


def find_system_dependencies(object_files):
    """
    Use :man:`dpkg-shlibdeps` to find dependencies on system packages.

    :param object_files: An iterable of strings with filenames of object files.
    :returns: A list of strings in the format of the entries on the
              ``Depends:`` line of a binary package control file.

    This function uses the :man:`dpkg-shlibdeps` program to find dependencies
    on system packages by analyzing the given object files (binary executables
    and/or ``*.so`` files). To find the object files you can use
    :func:`find_object_files()`.

    Here's an example to make things a bit more concrete:

    >>> find_system_dependencies(['/usr/bin/ssh'])
    ['libc6 (>= 2.17)',
     'libgssapi-krb5-2 (>= 1.12.1+dfsg-2)',
     'libselinux1 (>= 1.32)',
     'libssl1.0.0 (>= 1.0.1)',
     'zlib1g (>= 1:1.1.4)']

    Very advanced magic! :-)
    """
    logger.debug("Using `dpkg-shlibdeps' to find dependencies on system packages ..")
    # Create a fake source package because `dpkg-shlibdeps' requires it.
    directory = tempfile.mkdtemp()
    try:
        # Create the `debian' directory expected in the source package directory.
        os.mkdir(os.path.join(directory, 'debian'))
        # Create an empty `debian/control' file because `dpkg-shlibdeps' requires
        # this (even though it is apparently fine for the file to be empty ;-).
        with open(os.path.join(directory, 'debian', 'control'), 'w') as handle:
            handle.write('')
        # Run `dpkg-shlibdeps' inside the source package directory, but let it
        # analyze object files in a (build) directory managed by the caller.
        command = ['dpkg-shlibdeps', '-O']
        command.extend(map(os.path.abspath, object_files))
        output = execute(*command, capture=True, directory=directory, logger=logger, silent=True)
        expected_prefix = 'shlibs:Depends='
        if not output.startswith(expected_prefix):
            logger.warning(
                "The output of dpkg-shlibdeps doesn't match the"
                " expected format! (expected prefix: %r, output: %r)",
                expected_prefix, output,
            )
            return []
        output = output[len(expected_prefix):]
        dependencies = sorted(d.strip() for d in output.split(',') if d and not d.isspace())
        logger.debug("Dependencies reported by `dpkg-shlibdeps': %s", dependencies)
        return dependencies
    finally:
        shutil.rmtree(directory)


def find_object_files(directory):
    """
    Find binary executables and ``*.so`` files.

    :param directory: The pathname of the directory to search (a string).
    :returns: A list of filenames of object files (strings).

    This function is used by :func:`build_package()` to find files to process
    with :func:`find_system_dependencies()` and :func:`strip_object_files()`.
    It works by inspecting all of the files in the given `directory`:

    - If the filename matches ``*.so`` it is considered an object file.
    - If the file is marked executable and it contains binary data it is also
      considered an object file, unless the filename matches one of the
      patterns in :data:`OBJECT_FILE_EXCLUDES`.
    """
    binaries = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if not any(fnmatch.fnmatch(filename, p) for p in OBJECT_FILE_EXCLUDES):
                pathname = os.path.join(root, filename)
                if filename.endswith('.so') or (os.access(pathname, os.X_OK) and is_binary_file(pathname)):
                    binaries.append(pathname)
    return binaries


def is_binary_file(filename):
    """
    Check whether a file appears to contain binary data.

    :param filename: The filename of the file to check (a string).
    :returns: :data:`True` if the file appears to contain binary data,
              :data:`False` otherwise.
    """
    with open(filename, 'rb') as handle:
        return b'\0' in handle.read(1024 * 4)


def update_conffiles(directory):
    """
    Make sure the ``DEBIAN/conffiles`` file is up to date.

    :param directory: The pathname of a directory tree suitable for packaging
                      with ``dpkg-deb --build``.

    Given a directory tree suitable for packaging with ``dpkg-deb --build``
    this function updates the entries in the ``DEBIAN/conffiles`` file. This
    function is used by :func:`build_package()`.
    """
    conffiles = set()
    conffiles_file = os.path.join(directory, 'DEBIAN', 'conffiles')
    # Read the existing DEBIAN/conffiles entries (if any).
    if os.path.isfile(conffiles_file):
        logger.debug("Reading existing entries from %s ..", conffiles_file)
        with open(conffiles_file) as handle:
            for line in handle:
                filename = line.strip()
                pathname = os.path.join(directory, filename.lstrip('/'))
                # Validate existing entries.
                if os.path.isfile(pathname):
                    conffiles.add(filename)
                else:
                    logger.warning("Stripping invalid entry: %s", filename)
        os.unlink(conffiles_file)
    # Make sure all regular files in /etc/ are marked as configuration files.
    for root, dirs, files in os.walk(os.path.join(directory, 'etc')):
        for filename in files:
            pathname = os.path.join(root, filename)
            if os.path.isfile(pathname) and not os.path.islink(pathname):
                relpath = '/' + os.path.relpath(pathname, directory)
                if relpath not in conffiles:
                    logger.debug("Marking configuration file: %s", relpath)
                    conffiles.add(relpath)
    # Update DEBIAN/conffiles.
    if conffiles:
        with open(conffiles_file, 'w') as handle:
            for filename in sorted(conffiles):
                handle.write("%s\n" % filename)
        logger.debug("Wrote %s to %s!", pluralize(len(conffiles), "entry", "entries"), conffiles_file)


def update_installed_size(directory):
    """
    Make sure the ``Installed-Size`` field in ``DEBIAN/control`` is up to date.

    :param directory: The pathname of a directory tree suitable for packaging
                      with ``dpkg-deb --build``.

    Given a directory tree suitable for packaging with ``dpkg-deb --build``
    this function updates the Installed-Size_ field in the ``DEBIAN/control``
    file. This function is used by :func:`build_package()`.

    .. _Installed-Size: http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Installed-Size
    """
    # Find the installed size of the package (a rough estimate is fine).
    logger.debug("Finding installed size of package ..")
    output = execute('du', '-sk', directory, logger=logger, capture=True)
    installed_size = output.split()[0]
    # Patch the DEBIAN/control file.
    control_file = os.path.join(directory, 'DEBIAN', 'control')
    patch_control_file(control_file, {'Installed-Size': installed_size})
