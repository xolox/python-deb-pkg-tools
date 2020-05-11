# Debian packaging tools: Control file manipulation.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 11, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Functions to manipulate Debian control files.

The functions in the :mod:`deb_pkg_tools.control` module can be used to
manipulate Debian control files. It was developed specifically for control
files of binary packages, however the code is very generic.

This module makes extensive use of case insensitivity provided by the
:mod:`humanfriendly.case` module:

- The dictionaries returned by this module are case insensitive.
- The enumerations :data:`MANDATORY_BINARY_CONTROL_FIELDS` and
  :data:`DEPENDS_LIKE_FIELDS` contain case insensitive strings.

Case insensitivity was originally added to this module by virtue of its
integration with :pypi:`python-debian`. Since then this dependency was
removed but the case insensitive behavior was preserved for the sake
of backwards compatibility.
"""

# Standard library modules.
import logging
import os

# External dependencies.
from humanfriendly import format_path
from humanfriendly.case import CaseInsensitiveDict, CaseInsensitiveKey
from humanfriendly.deprecation import define_aliases
from humanfriendly.text import compact, concatenate, pluralize
from six import string_types, text_type

# Modules included in our package.
from deb_pkg_tools.deps import parse_depends, RelationshipSet
from deb_pkg_tools.utils import makedirs
from deb_pkg_tools.deb822 import Deb822, parse_deb822

# Public identifiers that require documentation.
__all__ = (
    "DEFAULT_CONTROL_FIELDS",
    "DEPENDS_LIKE_FIELDS",
    "MANDATORY_BINARY_CONTROL_FIELDS",
    "SPECIAL_CASES",
    "check_mandatory_fields",
    "create_control_file",
    "load_control_file",
    "logger",
    "merge_control_fields",
    "normalize_control_field_name",
    "parse_control_fields",
    "patch_control_file",
    "unparse_control_fields",
)

# Initialize a logger.
logger = logging.getLogger(__name__)

MANDATORY_BINARY_CONTROL_FIELDS = (
    CaseInsensitiveKey('Architecture'),
    CaseInsensitiveKey('Description'),
    CaseInsensitiveKey('Maintainer'),
    CaseInsensitiveKey('Package'),
    CaseInsensitiveKey('Version'),
)
"""
A tuple of strings (actually :class:`~humanfriendly.case.CaseInsensitiveKey`
objects) with the canonical names of the mandatory binary control file fields
as defined by the `Debian policy manual
<https://www.debian.org/doc/debian-policy/ch-controlfields.html#s-binarycontrolfiles>`_.
"""

DEFAULT_CONTROL_FIELDS = CaseInsensitiveDict(Architecture='all', Priority='optional', Section='misc')
"""
A case insensitive dictionary with string key/value pairs. Each key is the
canonical name of a binary control file field and each value is the default
value given to that field by :func:`create_control_file()` when the caller
hasn't defined a value for the field.
"""

DEPENDS_LIKE_FIELDS = (
    # Binary control file fields.
    CaseInsensitiveKey('Breaks'),
    CaseInsensitiveKey('Conflicts'),
    CaseInsensitiveKey('Depends'),
    CaseInsensitiveKey('Enhances'),
    CaseInsensitiveKey('Pre-Depends'),
    CaseInsensitiveKey('Provides'),
    CaseInsensitiveKey('Recommends'),
    CaseInsensitiveKey('Replaces'),
    CaseInsensitiveKey('Suggests'),
    # Source control file fields.
    CaseInsensitiveKey('Build-Conflicts'),
    CaseInsensitiveKey('Build-Conflicts-Arch'),
    CaseInsensitiveKey('Build-Conflicts-Indep'),
    CaseInsensitiveKey('Build-Depends'),
    CaseInsensitiveKey('Build-Depends-Arch'),
    CaseInsensitiveKey('Build-Depends-Indep'),
    CaseInsensitiveKey('Built-Using'),
)
"""
A tuple of strings with the canonical names of control file fields that are
similar to the ``Depends`` field (in the sense that they contain a comma
separated list of package names with optional version specifications).
"""

INSTALLED_SIZE_FIELD = CaseInsensitiveKey('Installed-Size')
"""A case insensitive string to match the "Installed-Size" field name."""

SPECIAL_CASES = dict(md5sum='MD5sum', sha1='SHA1', sha256='SHA256')
"""
A dictionary with string key/value pairs of non-default casing for words that
are part of control field names. The keys are intentionally normalized to
lowercase, whereas the values contain the proper casing. Used by
:func:`normalize_control_field_name()`.
"""


def load_control_file(control_file):
    """
    Load a control file and return the parsed control fields.

    :param control_file: The filename of the control file to load (a string).
    :returns: A dictionary created by :func:`parse_control_fields()`.
    """
    with open(control_file) as handle:
        shallow_parsed = parse_deb822(handle.read(), filename=control_file)
        return parse_control_fields(shallow_parsed)


def create_control_file(control_file, control_fields):
    """
    Create a Debian control file.

    :param control_file: The filename of the control file to create (a string).
    :param control_fields: A dictionary with control file fields. This
                           dictionary is merged with the values in
                           :data:`DEFAULT_CONTROL_FIELDS`.
    :raises: See :func:`check_mandatory_fields()`.
    """
    logger.debug("Creating control file: %s", format_path(control_file))
    # Merge the defaults with the fields defined by the caller.
    merged_fields = merge_control_fields(DEFAULT_CONTROL_FIELDS, control_fields)
    # Sanity check for mandatory fields that are missing.
    check_mandatory_fields(merged_fields)
    # Make sure the parent directory of the control file exists.
    makedirs(os.path.dirname(control_file))
    # Remove the control file if it already exists in case it's a hard link to
    # an inode with multiple hard links that should _not_ be changed by us.
    if os.path.exists(control_file):
        os.unlink(control_file)
    # Write the control file.
    with open(control_file, 'wb') as handle:
        merged_fields.dump(handle)


def check_mandatory_fields(control_fields):
    """
    Make sure mandatory binary control fields are defined.

    :param control_fields: A dictionary with control file fields.
    :raises: :exc:`~exceptions.ValueError` when a mandatory binary control
             field is not present in the provided control fields (see also
             :data:`MANDATORY_BINARY_CONTROL_FIELDS`).
    """
    missing_fields = [f for f in MANDATORY_BINARY_CONTROL_FIELDS if not control_fields.get(f)]
    if missing_fields:
        raise ValueError(compact(
            "Missing {fields}! ({details})",
            fields=pluralize(len(missing_fields), "mandatory binary package control field"),
            details=concatenate(sorted(missing_fields)),
        ))


def patch_control_file(control_file, overrides):
    """
    Patch the fields of a Debian control file.

    :param control_file: The filename of the control file to patch (a string).
    :param overrides: A dictionary with fields that should override default
                      name/value pairs. Values of the fields `Depends`,
                      `Provides`, `Replaces` and `Conflicts` are merged
                      while values of other fields are overwritten.
    """
    logger.debug("Patching control file: %s", format_path(control_file))
    # Read the control file.
    with open(control_file) as handle:
        defaults = parse_deb822(handle.read(), filename=control_file)
    # Apply the patches.
    patched = merge_control_fields(defaults, overrides)
    # Break the hard link chain.
    os.unlink(control_file)
    # Patch the control file.
    with open(control_file, 'wb') as handle:
        patched.dump(handle)


def merge_control_fields(defaults, overrides):
    """
    Merge the fields of two Debian control files.

    :param defaults: A dictionary with existing control field name/value pairs.
    :param overrides: A dictionary with fields that should override default
                      name/value pairs. Values of the fields `Depends`,
                      `Provides`, `Replaces` and `Conflicts` are merged
                      while values of other fields are overwritten.
    :returns: A dictionary of the type :class:`.Deb822`.
    """
    merged = Deb822()
    defaults = parse_control_fields(defaults)
    overrides = parse_control_fields(overrides)
    logger.debug("Merging control files (%i default fields, %i override fields)", len(defaults), len(overrides))
    # Merge the field names while preserving their order.
    field_names = list(defaults.keys())
    for name in overrides.keys():
        if name not in field_names:
            field_names.append(name)
    for name in field_names:
        if name in DEPENDS_LIKE_FIELDS:
            # Dependencies are merged instead of overridden.
            relationships = set()
            for source in [defaults, overrides]:
                if name in source:
                    relationships.update(source[name].relationships)
            merged[name] = RelationshipSet(*sorted(relationships))
        elif name not in overrides:
            merged[name] = defaults[name]
        elif name not in defaults:
            merged[name] = overrides[name]
        else:
            # Field present in both defaults and overrides;
            # in this case the override takes precedence.
            merged[name] = overrides[name]
    logger.debug("Merged control fields: %s", merged)
    return unparse_control_fields(merged)


def parse_control_fields(input_fields):
    r"""
    Parse Debian control file fields.

    :param input_fields: The dictionary to convert.
    :returns: A dictionary of the type :class:`.Deb822`.

    This function takes the result of the shallow parsing of control fields
    performed by :func:`.parse_deb822()` and massages the data into a
    friendlier format:

    - The values of the fields given by :data:`DEPENDS_LIKE_FIELDS` are parsed
      into Python data structures using :func:`.parse_depends()`.

    - The value of the `Installed-Size` field is converted to an integer.

    Let's look at an example. We start with the raw control file contents so
    you can see the complete input:

    >>> from deb_pkg_tools.deb822 import parse_deb822
    >>> unparsed_fields = parse_deb822('''
    ... Package: python3.4-minimal
    ... Version: 3.4.0-1+precise1
    ... Architecture: amd64
    ... Installed-Size: 3586
    ... Pre-Depends: libc6 (>= 2.15)
    ... Depends: libpython3.4-minimal (= 3.4.0-1+precise1), libexpat1 (>= 1.95.8), libgcc1 (>= 1:4.1.1), zlib1g (>= 1:1.2.0), foo | bar
    ... Recommends: python3.4
    ... Suggests: binfmt-support
    ... Conflicts: binfmt-support (<< 1.1.2)
    ... ''')

    Here are the control file fields as parsed by :func:`.parse_deb822()`:

    >>> print(repr(unparsed_fields))
    {'Architecture': u'amd64',
     'Conflicts': u'binfmt-support (<< 1.1.2)',
     'Depends': u'libpython3.4-minimal (= 3.4.0-1+precise1), libexpat1 (>= 1.95.8), libgcc1 (>= 1:4.1.1), zlib1g (>= 1:1.2.0), foo | bar',
     'Installed-Size': u'3586',
     'Package': u'python3.4-minimal',
     'Pre-Depends': u'libc6 (>= 2.15)',
     'Recommends': u'python3.4',
     'Suggests': u'binfmt-support',
     'Version': u'3.4.0-1+precise1'}

    Notice the value of the `Depends` line is a comma separated string, i.e. it
    hasn't been parsed. Now here are the control file fields parsed by the
    :func:`parse_control_fields()` function:

    >>> from deb_pkg_tools.control import parse_control_fields
    >>> parsed_fields = parse_control_fields(unparsed_fields)
    >>> print(repr(parsed_fields))
    {'Architecture': u'amd64',
     'Conflicts': RelationshipSet(VersionedRelationship(name=u'binfmt-support', operator=u'<<', version=u'1.1.2')),
     'Depends': RelationshipSet(VersionedRelationship(name=u'libpython3.4-minimal', operator=u'=', version=u'3.4.0-1+precise1'),
                                VersionedRelationship(name=u'libexpat1', operator=u'>=', version=u'1.95.8'),
                                VersionedRelationship(name=u'libgcc1', operator=u'>=', version=u'1:4.1.1'),
                                VersionedRelationship(name=u'zlib1g', operator=u'>=', version=u'1:1.2.0'),
                                AlternativeRelationship(Relationship(name=u'foo'), Relationship(name=u'bar'))),
     'Installed-Size': 3586,
     'Package': u'python3.4-minimal',
     'Pre-Depends': RelationshipSet(VersionedRelationship(name=u'libc6', operator=u'>=', version=u'2.15')),
     'Recommends': u'python3.4',
     'Suggests': RelationshipSet(Relationship(name=u'binfmt-support')),
     'Version': u'3.4.0-1+precise1'}

    For more information about fields like `Depends` and `Suggests` please
    refer to the documentation of :func:`.parse_depends()`.
    """
    output_fields = Deb822()
    logger.debug("Parsing %i control fields ..", len(input_fields))
    for name, unparsed_value in input_fields.items():
        name = normalize_control_field_name(name)
        if name in DEPENDS_LIKE_FIELDS:
            parsed_value = parse_depends(unparsed_value)
        elif name == INSTALLED_SIZE_FIELD:
            parsed_value = int(unparsed_value)
        else:
            parsed_value = unparsed_value
        output_fields[name] = parsed_value
    logger.debug("Parsed fields: %s", output_fields)
    return output_fields


def unparse_control_fields(input_fields):
    """
    Unparse (undo the parsing of) Debian control file fields.

    :param input_fields: A :class:`dict` object previously returned by
                         :func:`parse_control_fields()`.
    :returns: A dictionary of the type :class:`.Deb822`.

    This function converts dictionaries created by
    :func:`parse_control_fields()` back into shallow dictionaries of strings.
    Fields with an empty value are omitted. This makes it possible to delete
    fields from a control file with :func:`patch_control_file()` by setting the
    value of a field to :data:`None` in the overrides...
    """
    output_fields = Deb822()
    logger.debug("Unparsing %i control fields ..", len(input_fields))
    for name, parsed_value in input_fields.items():
        name = normalize_control_field_name(name)
        if name in DEPENDS_LIKE_FIELDS:
            if isinstance(parsed_value, RelationshipSet):
                # New interface (a RelationshipSet object).
                unparsed_value = text_type(parsed_value)
            elif not isinstance(parsed_value, string_types):
                # Backwards compatibility  with old interface (list of strings).
                unparsed_value = u', '.join(parsed_value)
            else:
                # Compatibility with callers that set one of the Depends-like
                # fields to a string value (which is fine).
                unparsed_value = parsed_value
        elif name == INSTALLED_SIZE_FIELD:
            unparsed_value = str(parsed_value)
        else:
            unparsed_value = parsed_value
        if unparsed_value:
            output_fields[name] = unparsed_value
    logger.debug("Unparsed fields: %r", output_fields)
    return output_fields


def normalize_control_field_name(name):
    """
    Normalize the case of a field name in a Debian control file.

    :param name: The name of a control file field (a string).
    :returns: The normalized name (a string of the type :class:`~humanfriendly.case.CaseInsensitiveKey`).

    Normalization of control file field names is useful to simplify control
    file manipulation and in particular the merging of control files.

    According to the Debian Policy Manual (section 5.1, `Syntax of control
    files`_) field names are not case-sensitive, however in my experience
    deviating from the standard capitalization can break things. Hence this
    function (which is used by the other functions in the
    :mod:`deb_pkg_tools.control` module).

    .. note:: This function doesn't adhere 100% to the Debian policy because it
              lacks special casing (no pun intended ;-) for fields like
              ``DM-Upload-Allowed``. It's not clear to me if this will ever
              become a relevant problem for building simple binary packages...
              (which explains why I didn't bother to implement special casing)

    .. _Syntax of control files: http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-controlsyntax
    """
    return CaseInsensitiveKey(u'-'.join(SPECIAL_CASES.get(w.lower(), w.capitalize()) for w in name.split(u'-')))


# Define aliases for backwards compatibility.
define_aliases(
    module_name=__name__,
    # In deb-pkg-tools 8.0 the python-debian integration was removed and
    # the required functionality was implemented as part of deb-pkg-tools.
    deb822_from_string='deb_pkg_tools.deb822.parse_deb822',
    Deb822='deb_pkg_tools.deb822.Deb822',
)
