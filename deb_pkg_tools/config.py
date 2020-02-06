# Debian packaging tools: Configuration defaults.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: February 6, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""Configuration defaults for the `deb-pkg-tools` package."""

# Standard library modules.
import os

# External dependencies.
from humanfriendly import parse_path

# Public identifiers that require documentation.
__all__ = (
    "package_cache_directory",
    "repo_config_file",
    "system_cache_directory",
    "system_config_directory",
    "user_cache_directory",
    "user_config_directory",
)

system_config_directory = '/etc/deb-pkg-tools'
"""The pathname of the global (system wide) configuration directory used by `deb-pkg-tools` (a string)."""

system_cache_directory = '/var/cache/deb-pkg-tools'
"""The pathname of the global (system wide) package cache directory (a string)."""

user_config_directory = parse_path('~/.deb-pkg-tools')
"""
The pathname of the current user's configuration directory used by `deb-pkg-tools` (a string).

:default: The expanded value of ``~/.deb-pkg-tools``.
"""

user_cache_directory = parse_path('~/.cache/deb-pkg-tools')
"""
The pathname of the current user's package cache directory (a string).

:default: The expanded value of ``~/.cache/deb-pkg-tools``.
"""

# The location of the package cache. If we're running as root we have write
# access to the system wide package cache so we'll pick that; the more users
# sharing this cache the more effective it is.

package_cache_directory = system_cache_directory if os.getuid() == 0 else user_cache_directory
"""
The pathname of the selected package cache directory (a string).

:default: The value of :data:`system_cache_directory` when running as ``root``,
          the value of :data:`user_cache_directory` otherwise.
"""

repo_config_file = 'repos.ini'
"""
The base name of the configuration file with user-defined Debian package repositories (a string).

This configuration file is loaded from :data:`system_config_directory` and/or
:data:`user_config_directory`.

:default: The string ``repos.ini``.
"""
