# Debian packaging tools: Version comparison and sorting.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: April 19, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Version comparison and sorting according to Debian semantics.

The :mod:`deb_pkg_tools.version` module supports version comparison and sorting
according to `section 5.6.12 of the Debian Policy Manual`_. The main entry
points for users of the Python API are the :func:`compare_versions()` function
and the :class:`Version` class.

This module contains two Debian version comparison implementations:

:func:`compare_versions_native()`
 This is a pure Python implementation of the Debian version sorting algorithm.
 It's the default choice of :func:`compare_versions()` for performance reasons.

:func:`compare_versions_external()`
 This works by running the external command ``dpkg --compare-versions``. It's
 provided only as an alternative to fall back on should issues come to light
 with the implementation of :func:`compare_versions_native()`, for more on that
 please refer to :data:`PREFER_DPKG`.

.. _section 5.6.12 of the Debian Policy Manual: http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Version
"""

# Standard library modules.
import logging
import os

# External dependencies.
from executor import execute
from humanfriendly import coerce_boolean
from humanfriendly.deprecation import define_aliases

# Modules included in our package.
from deb_pkg_tools.version.native import compare_version_objects

# Public identifiers that require documentation.
__all__ = (
    'DPKG_COMPARISON_CACHE',
    'NATIVE_COMPARISON_CACHE',
    'PREFER_DPKG',
    'Version',
    'coerce_version',
    'compare_versions',
    'compare_versions_native',
    'compare_versions_external',
    'logger',
)

PREFER_DPKG = coerce_boolean(os.environ.get('DPT_VERSION_COMPAT', 'false'))
"""
:data:`True` to prefer :func:`compare_versions_external()` over
:func:`compare_versions_native()`, :data:`False` otherwise (the
default is :data:`False`).

The environment variable ``$DPT_VERSION_COMPAT`` can be used to control the
value of this variable (see :func:`~humanfriendly.coerce_boolean()` for
acceptable values).

.. note:: This option was added in preparation for release 8.0 which
          replaces python-apt_ based version comparison with a pure Python
          implementation that -although tested- definitely has the potential to
          cause regressions. If regressions do surface this option provides an
          easy to use "escape hatch" to restore compatibility.

.. _python-apt: https://packages.debian.org/python-apt
"""

DPKG_COMPARISON_CACHE = {}
"""
This dictionary is used by :func:`compare_versions_external()` to cache ``dpkg
--compare-versions`` results. Each key in the dictionary is a tuple of three
values: (version1, operator, version2). Each value in the dictionary is a
boolean (:data:`True` if the comparison succeeded, :data:`False` if it failed).
"""

NATIVE_COMPARISON_CACHE = {}
"""
This dictionary is used by :func:`compare_versions_native()` to cache the
results of comparisons between version strings. Each key in the dictionary is a
tuple of two values: (version1, version2). Each value is one of the following
integers:

- -1 means version1 sorts before version2
- 0 means version1 and version2 are equal
- 1 means version1 sorts after version2

This cache is a lot more efficient than :data:`DPKG_COMPARISON_CACHE` because
the cache key doesn't contain operators.
"""

# Initialize a logger.
logger = logging.getLogger(__name__)


def coerce_version(value):
    """
    Coerce strings to :class:`Version` objects.

    :param value: The value to coerce (a string or :class:`Version` object).
    :returns: A :class:`Version` object.
    """
    if not isinstance(value, Version):
        value = Version(value)
    return value


def compare_versions(version1, operator, version2):
    """
    Compare Debian package versions using the best available method.

    :param version1: The version on the left side of the comparison (a string).
    :param operator: The operator to use in the comparison (a string).
    :param version2: The version on the right side of the comparison (a string).
    :returns: :data:`True` if the comparison succeeds, :data:`False` if it fails.

    This function prefers to use :func:`compare_versions_native()` but will use
    :func:`compare_versions_external()` instead when :data:`PREFER_DPKG` is
    :data:`True`.
    """
    if PREFER_DPKG:
        return compare_versions_external(version1, operator, version2)
    else:
        return compare_versions_native(version1, operator, version2)


def compare_versions_external(version1, operator, version2):
    """
    Compare Debian package versions using the external command ``dpkg --compare-versions ...``.

    :param version1: The version on the left side of the comparison (a string).
    :param operator: The operator to use in the comparison (a string).
    :param version2: The version on the right side of the comparison (a string).
    :returns: :data:`True` if the comparison succeeds, :data:`False` if it fails.

    .. seealso:: :data:`DPKG_COMPARISON_CACHE` and :data:`PREFER_DPKG`
    """
    # Check if the result of this comparison is in the cache.
    cache_key = (version1, operator, version2)
    try:
        return DPKG_COMPARISON_CACHE[cache_key]
    except KeyError:
        pass
    # Call out to /usr/bin/dpkg to perform the comparison.
    result = execute('dpkg', '--compare-versions', version1, operator, version2, check=False)
    # Store the result in the cache.
    DPKG_COMPARISON_CACHE[cache_key] = result
    # Report the result to the caller.
    return result


def compare_versions_native(version1, operator, version2):
    """
    Compare Debian package versions using a pure Python implementation.

    :param version1: The version on the left side of the comparison (a string).
    :param operator: The operator to use in the comparison (a string).
    :param version2: The version on the right side of the comparison (a string).
    :returns: :data:`True` if the comparison succeeds, :data:`False` if it fails.

    .. seealso:: :data:`NATIVE_COMPARISON_CACHE` and :func:`.compare_version_objects()`
    """
    # Compare the two version numbers and remember the result so that
    # we don't have to compare two version numbers more than once.
    key = (version1, version2)
    try:
        value = NATIVE_COMPARISON_CACHE[key]
    except KeyError:
        version1 = coerce_version(version1)
        version2 = coerce_version(version2)
        value = compare_version_objects(version1, version2)
        NATIVE_COMPARISON_CACHE[key] = value
    # Translate the comparison result to the requested operator.
    if operator == '=':
        # Equality.
        return value == 0
    elif operator == '<<':
        # Strictly less than.
        return value < 0
    elif operator == '>>':
        # Strictly more than.
        return value > 0
    elif operator == '<' or operator == '<=':
        # Less than or equal.
        return value <= 0
    elif operator == '>' or operator == '>=':
        # More than or equal.
        return value >= 0
    else:
        msg = "Unsupported Debian version number comparison operator! (%s)"
        raise ValueError(msg % operator)


class Version(str):

    """
    Rich comparison of Debian package versions as first-class Python objects.

    The :class:`Version` class is a subclass of the built in :class:`str` type
    that implements rich comparison according to the version sorting order
    defined in the Debian Policy Manual. Use it to sort Debian package versions
    like this:

      >>> from deb_pkg_tools.version import Version
      >>> unsorted = ['0.1', '0.5', '1.0', '2.0', '3.0', '1:0.4', '2:0.3']
      >>> print(sorted(Version(s) for s in unsorted))
      ['0.1', '0.5', '1.0', '2.0', '3.0', '1:0.4', '2:0.3']

    This example uses 'epoch' numbers (the numbers before the colons) to
    demonstrate that this version sorting order is different from regular
    sorting and 'natural order sorting'.

    .. attribute:: epoch

       The integer value of the epoch number specified by the version string
       (defaults to zero in case the Debian version number doesn't specify an
       epoch number).

    .. attribute:: upstream_version

       A string containing the main version number component that encodes the
       upstream version number.

    .. attribute:: debian_revision

       A string containing the Debian revision suffixed to the version number.
    """

    def __init__(self, value):
        """
        Initialize a :class:`Version` object.

        :param value: A string containing a Debian version number.
        """
        if ":" in value:
            epoch, _, value = value.partition(":")
            self.epoch = int(epoch)
        else:
            self.epoch = 0
        if "-" in value:
            upstream, _, debian = value.rpartition("-")
            self.upstream_version = upstream
            self.debian_revision = debian
        else:
            self.upstream_version = value
            self.debian_revision = ""

    def __hash__(self):
        """Enable adding :class:`Version` objects to sets and using them as dictionary keys."""
        try:
            return self._cached_hash
        except AttributeError:
            value = hash((self.epoch, self.upstream_version, self.debian_revision))
            self._cached_hash = value
            return value

    def __eq__(self, other):
        """Enable equality comparison between :class:`Version` objects."""
        if type(self) is type(other):
            return (
                (self.epoch == other.epoch)
                and (self.upstream_version == other.upstream_version)
                and (self.debian_revision == other.debian_revision)
            )
        else:
            return NotImplemented

    def __ne__(self, other):
        """Enable non-equality comparison between version objects."""
        return not compare_versions(self, '=', other) if type(self) is type(other) else NotImplemented

    def __lt__(self, other):
        """Enable less-than comparison between version objects."""
        return compare_versions(self, '<<', other) if type(self) is type(other) else NotImplemented

    def __le__(self, other):
        """Enable less-than-or-equal comparison between version objects."""
        return compare_versions(self, '<=', other) if type(self) is type(other) else NotImplemented

    def __gt__(self, other):
        """Enable greater-than comparison between version objects."""
        return compare_versions(self, '>>', other) if type(self) is type(other) else NotImplemented

    def __ge__(self, other):
        """Enable greater-than-or-equal comparison between version objects."""
        return compare_versions(self, '>=', other) if type(self) is type(other) else NotImplemented


# Define aliases for backwards compatibility.
define_aliases(
    module_name=__name__,
    # In deb-pkg-tools 8.0 this function was renamed.
    compare_versions_with_dpkg='deb_pkg_tools.version.compare_versions_external',
    # In deb-pkg-tools 8.0 the python-apt integration was removed so
    # technically we can no longer satisfy this import, however we can
    # offer a functionally equivalent implementation (albeit much slower).
    compare_versions_with_python_apt='deb_pkg_tools.version.compare_versions_external',
    # In deb-pkg-tools 8.0 this module variable was renamed.
    dpkg_comparison_cache='deb_pkg_tools.version.DPKG_COMPARISON_CACHE',
)
