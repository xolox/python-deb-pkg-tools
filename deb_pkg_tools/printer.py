# Debian packaging tools: Custom pretty printer.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 22, 2016
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Custom pretty printer for parsed control files and package relationships.

The :class:`PrettyPrinter` class in the :mod:`deb_pkg_tools.print` module can
be used to pretty print Python expressions containing :class:`debian.deb822.Deb822`
and/or :class:`deb_pkg_tools.deps.RelationshipSet` objects.

The custom pretty printer is useful during testing and documenting, for example
the :mod:`doctest` fragments spread throughout the :mod:`deb_pkg_tools`
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

    """Custom pretty printer for parsed control files and package relationships."""

    def _format(self, obj, stream, indent, *args):
        if isinstance(obj, RelationshipSet):
            stream.write(obj.__repr__(indent=indent, pretty=True))
        elif isinstance(obj, Deb822):
            pprint.PrettyPrinter._format(self, dict(obj), stream, indent, *args)
        else:
            pprint.PrettyPrinter._format(self, obj, stream, indent, *args)
