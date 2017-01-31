# Debian packaging tools: Compatibility functions.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: January 27, 2017
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Python version compatibility.

The :mod:`deb_pkg_tools.compat` module makes it easier to write Python code
that is compatible with Python 2.6 up to 3.5, filling in some missing bits that
`six <http://six.readthedocs.org/>`_ doesn't provide.
"""

# External dependencies.
from six import PY2


def str_compatible(cls):
    """
    A class decorator that defines ``__unicode__()`` and ``__str__()`` on Python 2.

    :param cls: The class to decorate.
    :returns: The decorated class.

    On Python 3 this class decorator does nothing, in the assumption that the
    class defines an ``__str__()`` method and that is all that is needed.

    On Python 2 the ``__unicode__()`` method is defined based on the
    implementation of ``__str__()`` and then ``__str__()`` is redefined to
    return the UTF-8 encoded result of ``__unicode__()``.
    """
    if PY2:
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda self: self.__unicode__().encode('UTF-8')
    return cls
