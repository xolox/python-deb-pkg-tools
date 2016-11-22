# Debian packaging tools: Compatibility functions.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 21, 2016
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


def total_ordering(cls):
    """
    Class decorator that fills in missing ordering methods.

    Copied from :func:`functools.total_ordering()` which became available in
    Python 2.7 (copied to enable compatibility with Python 2.6).
    """
    convert = {
        '__lt__': [('__gt__', lambda self, other: not (self < other or self == other)),
                   ('__le__', lambda self, other: self < other or self == other),
                   ('__ge__', lambda self, other: not self < other)],
        '__le__': [('__ge__', lambda self, other: not self <= other or self == other),
                   ('__lt__', lambda self, other: self <= other and not self == other),
                   ('__gt__', lambda self, other: not self <= other)],
        '__gt__': [('__lt__', lambda self, other: not (self > other or self == other)),
                   ('__ge__', lambda self, other: self > other or self == other),
                   ('__le__', lambda self, other: not self > other)],
        '__ge__': [('__le__', lambda self, other: (not self >= other) or self == other),
                   ('__gt__', lambda self, other: self >= other and not self == other),
                   ('__lt__', lambda self, other: not self >= other)]
    }
    roots = set(dir(cls)) & set(convert)
    if not roots:
        raise ValueError('must define at least one ordering operation: < > <= >=')
    root = max(roots)       # prefer __lt__ to __le__ to __gt__ to __ge__
    for opname, opfunc in convert[root]:
        if opname not in roots:
            opfunc.__name__ = opname
            opfunc.__doc__ = getattr(int, opname).__doc__
            setattr(cls, opname, opfunc)
    return cls
