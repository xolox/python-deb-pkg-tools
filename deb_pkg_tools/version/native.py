# Debian packaging tools: Version comparison and sorting.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: April 19, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Pure Python implementation of Debian version comparison and sorting.

The :mod:`deb_pkg_tools.version` module previously integrated with python-apt_,
however it was pointed out to me in `issue #20`_ that python-apt_ uses the GPL2
license. Because GPL2 is a viral license it dictates that :pypi:`deb-pkg-tools`
also needs to be published under GPL2. Because I didn't feel like switching
from MIT to GPL I decided to remove the dependency instead (switching would
have cascaded down to several other Python packages I've published and I wasn't
comfortable with that).

While working on this pure Python implementation I was initially worried about
performance being much worse than using python-apt_, so much so that I'd
already started researching how to implement a binary "speedup" module. Imagine
my surprise when I started running benchmarks and found that my pure Python
implementation was (just slightly) faster than python-apt_!

.. _python-apt: https://packages.debian.org/python-apt
.. _issue #20: https://github.com/xolox/python-deb-pkg-tools/issues/20
"""

# Standard library modules.
import logging
import string

# External dependencies.
from humanfriendly.decorators import cached
from six.moves import zip_longest

# Public identifiers that require documentation.
__all__ = (
    'compare_version_objects',
    'compare_strings',
    'get_digit_prefix',
    'get_non_digit_prefix',
    'get_order_mapping',
    'logger',
)

# Initialize a logger.
logger = logging.getLogger(__name__)


def compare_strings(version1, version2):
    """
    Compare two upstream version strings or Debian revision strings.

    :param version1: An upstream version string or Debian revision string.
    :param version2: An upstream version string or Debian revision string.
    :returns: One of the following integer numbers:

              - -1 means version1 sorts before version2
              - 0 means version1 and version2 are equal
              - 1 means version1 sorts after version2

    This function is used by :func:`compare_version_objects()` to perform the
    comparison of Debian version strings.
    """
    logger.debug("Comparing Debian version number substrings %r and %r ..", version1, version2)
    mapping = get_order_mapping()
    v1 = list(version1)
    v2 = list(version2)
    while v1 or v2:
        # Quoting from the 'deb-version' manual page: First the initial part of each
        # string consisting entirely of non-digit characters is determined. These two
        # parts (one of which may be empty) are compared lexically. If a difference is
        # found it is returned. The lexical comparison is a comparison of ASCII values
        # modified so that all the letters sort earlier than all the non-letters and so
        # that a tilde sorts before anything, even the end of a part. For example, the
        # following parts are in sorted order: '~~', '~~a', '~', the empty part, 'a'.
        p1 = get_non_digit_prefix(v1)
        p2 = get_non_digit_prefix(v2)
        if p1 != p2:
            logger.debug("Comparing non-digit prefixes %r and %r ..", p1, p2)
            for c1, c2 in zip_longest(p1, p2, fillvalue=""):
                logger.debug("Performing lexical comparison between characters %r and %r ..", c1, c2)
                o1 = mapping.get(c1)
                o2 = mapping.get(c2)
                if o1 < o2:
                    logger.debug("Determined that %r sorts before %r (based on lexical comparison).", version1, version2)
                    return -1
                elif o1 > o2:
                    logger.debug("Determined that %r sorts after %r (based on lexical comparison).", version1, version2)
                    return 1
        elif p1:
            logger.debug("Skipping matching non-digit prefix %r ..", p1)
        # Quoting from the 'deb-version' manual page: Then the initial part of the
        # remainder of each string which consists entirely of digit characters is
        # determined. The numerical values of these two parts are compared, and any
        # difference found is returned as the result of the comparison. For these purposes
        # an empty string (which can only occur at the end of one or both version strings
        # being compared) counts as zero.
        d1 = get_digit_prefix(v1)
        d2 = get_digit_prefix(v2)
        logger.debug("Comparing numeric prefixes %i and %i ..", d1, d2)
        if d1 < d2:
            logger.debug("Determined that %r sorts before %r (based on numeric comparison).", version1, version2)
            return -1
        elif d1 > d2:
            logger.debug("Determined that %r sorts after %r (based on numeric comparison).", version1, version2)
            return 1
        else:
            logger.debug("Determined that numeric prefixes match.")
    logger.debug("Determined that version numbers are equal.")
    return 0


def compare_version_objects(version1, version2):
    """
    Compare two :class:`.Version` objects.

    :param version1: The version on the left side of the comparison (a :class:`.Version` object).
    :param version2: The version on the right side of the comparison (a :class:`.Version` object).
    :returns: One of the following integer numbers:

              - -1 means version1 sorts before version2
              - 0 means version1 and version2 are equal
              - 1 means version1 sorts after version2

    This function is used by :func:`~deb_pkg_tools.version.compare_versions_native()`
    to perform the comparison of Debian version strings, after which the operator is
    interpreted by :func:`~deb_pkg_tools.version.compare_versions_native()`.
    """
    logger.debug("Comparing Debian version numbers %r and %r ..", version1, version2)
    # Handle differences in the "epoch".
    if version1.epoch < version2.epoch:
        logger.debug("Determined that %r sorts before %r (epoch is lower).", version1, version2)
        return -1
    if version1.epoch > version2.epoch:
        logger.debug("Determined that %r sorts after %r (epoch is higher).", version1, version2)
        return 1
    # Handle differences in the "upstream version".
    result = compare_strings(version1.upstream_version, version2.upstream_version)
    if result != 0:
        return result
    # Handle differences in the "Debian revision".
    if version1.debian_revision or version2.debian_revision:
        return compare_strings(version1.debian_revision, version2.debian_revision)
    return 0


def get_digit_prefix(characters):
    """
    Get the digit prefix from a given list of characters.

    :param characters: A list of characters.
    :returns: An integer number (defaults to zero).

    Used by :func:`compare_strings()` as part of the implementation of
    :func:`~deb_pkg_tools.version.compare_versions_native()`.
    """
    value = 0
    while characters and characters[0].isdigit():
        value = value * 10 + int(characters.pop(0))
    return value


def get_non_digit_prefix(characters):
    """
    Get the non-digit prefix from a given list of characters.

    :param characters: A list of characters.
    :returns: A list of leading non-digit characters (may be empty).

    Used by :func:`compare_strings()` as part of the implementation of
    :func:`~deb_pkg_tools.version.compare_versions_native()`.
    """
    prefix = []
    while characters and not characters[0].isdigit():
        prefix.append(characters.pop(0))
    return prefix


@cached
def get_order_mapping():
    """
    Generate a mapping of characters to integers representing sorting order.

    :returns: A dictionary with string keys and integer values.

    Used by :func:`compare_strings()` as part of the implementation of
    :func:`~deb_pkg_tools.version.compare_versions_native()`.
    """
    ordered = []
    # The tilde sorts before everything.
    ordered.append("~")
    # The empty string sort before everything except a tilde.
    ordered.append("")
    # Letters sort before everything but a tilde or empty string, in their regular lexical sort order.
    ordered.extend(sorted(l for l in string.ascii_letters))
    # Punctuation characters follow in their regular lexical sort order.
    ordered.extend(sorted(set(string.punctuation) - set(["~"])))
    # Convert the list to a mapping from characters to indexes.
    return dict((c, i) for i, c in enumerate(ordered))
