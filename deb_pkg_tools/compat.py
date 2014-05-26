# Debian packaging tools: Compatibility functions.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 26, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Compatibility functions
=======================

The :py:mod:`deb_pkg_tools.compat` module makes it easier to write Python code
that is compatible with Python 2.x and Python 3.x. Think of it as a very
lightweight six_, except this module implements similar but different shortcuts
(the ones I need :-).

.. _six: http://six.readthedocs.org/
"""

import sys

# StringIO.StringIO() vs io.StringIO().
try:
    # Python 2.x.
    from StringIO import StringIO
except ImportError:
    # Python 3.x.
    from io import StringIO

# unicode() vs str().
try:
    unicode = unicode
except NameError:
    unicode = str

# str() vs basestring().
try:
    basestring = basestring
except NameError:
    basestring = str

def str_compatible(cls):
    """
    Class decorator that makes it easy to implement human readable object
    representations containing Unicode characters that are compatible with both
    Python 2.x (with its :py:func:`object.__unicode__()` and
    :py:func:`object.__str__()` methods) and Python 3.x (with its
    :py:func:`object.__str__()` and :py:func:`object.__bytes__()` methods).

    This decorator expects the ``__unicode__()`` method to return a Unicode
    string (i.e. you write Python 2.x compatible code). The missing part will
    be filled in automatically by encoding the Unicode string to UTF-8.
    """
    if sys.version_info[0] == 2:
        cls.__str__ = lambda self: unicode(self).encode('utf-8')
    elif sys.version_info[0] == 3:
        cls.__str__ = cls.__unicode__
        cls.__bytes__ = lambda self: str(self).encode('utf-8')
    return cls

def total_ordering(cls):
    """
    Class decorator that fills in missing ordering methods. Copied from
    :py:func:`functools.total_ordering()` which became available in Python
    2.7 (copied to enable compatibility with Python 2.6).
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

# vim: ts=4 sw=4 et
