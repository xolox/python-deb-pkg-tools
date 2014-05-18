# Debian packaging tools: Custom pretty printer.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 18, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Custom pretty printer
=======================

The :py:class:`PrettyPrinter` class in the :py:mod:`deb_pkg_tools.print`
module can be used to pretty print Python expressions containing
:py:class:`debian.deb822.Deb822` and/or
:py:class:`deb_pkg_tools.deps.RelationshipSet` objects.

The custom pretty printer is useful during testing and documenting, for example
the :py:mod:`doctest` fragments spread throughout the :py:mod:`deb_pkg_tools`
documentation use the custom pretty printer for human friendly object
representations.
"""

# Standard library modules.
import pprint

# Modules included in our package.
from deb_pkg_tools.deps import RelationshipSet

# External dependencies.
from debian.deb822 import Deb822

class CustomPrettyPrinter(pprint.PrettyPrinter):

    """
    Custom pretty printer that can be used to pretty print Python
    expressions containing :py:class:`debian.deb822.Deb822` and/or
    :py:class:`deb_pkg_tools.deps.RelationshipSet` objects.
    """

    def _format(self, obj, stream, indent, *args):
        if isinstance(obj, RelationshipSet):
            stream.write(obj.__repr__(indent=indent))
        elif isinstance(obj, Deb822):
            pprint.PrettyPrinter._format(self, dict(obj), stream, indent, *args)
        else:
            pprint.PrettyPrinter._format(self, obj, stream, indent, *args)

# vim: ts=4 sw=4 et
