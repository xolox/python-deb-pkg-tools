# Debian packaging tools: Control file manipulation.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 2, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""Parsing and formatting of Debian control fields in the :man:`deb822` format."""

# Standard library modules.
import codecs
import logging
import textwrap

# External dependencies.
from humanfriendly.case import CaseInsensitiveDict
from humanfriendly.text import compact, is_empty_line
from six import text_type

# Public identifiers that require documentation.
__all__ = ("Deb822", "dump_deb822", "logger", "parse_deb822")

# Initialize a logger.
logger = logging.getLogger(__name__)


def dump_deb822(fields):
    """
    Format the given Debian control fields as text.

    :param fields: The control fields to dump (a dictionary).
    :returns: A Unicode string containing the formatted control fields.
    """
    lines = []
    for key, value in fields.items():
        # Check for multi-line values.
        if "\n" in value:
            input_lines = value.splitlines()
            output_lines = [input_lines.pop(0)]
            for line in input_lines:
                if line and not line.isspace():
                    # Make sure continuation lines are indented.
                    output_lines.append(u" " + line)
                else:
                    # Encode empty continuation lines as a dot (indented).
                    output_lines.append(u" .")
            value = u"\n".join(output_lines)
        lines.append(u"%s: %s\n" % (key, value))
    return u"".join(lines)


def parse_deb822(text):
    """
    Parse Debian control fields into a :class:`Deb822` object.

    :param text: A string containing the control fields to parse.
    :returns: A :class:`Deb822` object.
    """
    # Make sure we're dealing with Unicode text.
    if not isinstance(text, text_type):
        text = codecs.decode(text, "UTF-8")
    # The following is not part of the deb822 standard - it was added to
    # deb-pkg-tools for convenient use in the test suite with indented string
    # literals. It's preserved for backwards compatibility, but may be removed
    # in the future.
    text = textwrap.dedent(text).strip()
    # Get ready to parse the control fields.
    input_lines = text.splitlines()
    parsed_fields = []
    while input_lines:
        line = input_lines.pop(0)
        # Completely ignore comment lines (even nested between "continuation lines").
        if line.startswith(u"#"):
            continue
        # Guard against empty lines that end the current "paragraph".
        if is_empty_line(line):
            # Check whether any input text remains.
            remainder = u"\n".join(input_lines)
            if not is_empty_line(remainder):
                raise ValueError(
                    compact(
                        """
                        Failed to parse control fields: Encountered end of
                        paragraph before end of input! (remaining text is %r)
                        """,
                        remainder,
                    )
                )
            break
        # Check for "continuation lines".
        if line.startswith((u" ", u"\t")) and not line.isspace():
            # Make sure the continuation line follows a key.
            if not parsed_fields:
                raise ValueError(
                    compact(
                        """
                        Failed to parse control fields: Got continuation
                        line without leading key! (current line is %r)
                        """,
                        line,
                    )
                )
            # Continuation lines containing only a dot are converted to empty lines.
            line = line.strip()
            if line == u".":
                line = u""
            # Store the continuation line under the preceding key.
            parsed_fields[-1][1].append(line)
        else:
            # Try to split the line into a key and value.
            key, delimiter, value = line.partition(":")
            # Validate the key by making sure there's a delimiter
            # (the value may be empty so we can't check that).
            if not (key and delimiter):
                raise ValueError(
                    compact(
                        """
                        Failed to parse control fields: Line not recognized as
                        key/value pair or continuation line! (current line is %r)
                        """,
                        line,
                    )
                )
            # We succeeded! Store the resulting tokens.
            parsed_fields.append((key.strip(), [value.strip()]))
    # Convert the data structure we've built up to a dictionary.
    return Deb822((key, "\n".join(lines)) for key, lines in parsed_fields)


class Deb822(CaseInsensitiveDict):

    """
    Case insensitive dictionary to represent the fields of a parsed :man:`deb822` paragraph.

    This class imitates the class of the same name in the :pypi:`python-debian`
    package, primarily in the form of the :func:`dump()` method, however that's
    also where the similarities end (full compatibility is not a goal).
    """

    def dump(self, handle=None):
        """
        Dump the control fields to a file.

        :param handle: A file-like object or :data:`None`.
        :returns: If `handle` is :data:`None` the dumped control fields are
                  returned as a Unicode string.
        """
        text = dump_deb822(self)
        if handle is not None:
            handle.write(text.encode("UTF-8"))
        else:
            return text

    def __eq__(self, other):
        """Compare two :class:`Deb822` objects while ignoring differences in the order of keys."""
        return dict(self) == dict(other)
