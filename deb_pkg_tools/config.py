# Debian packaging tools: Configuration defaults.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: September 17, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Configuration defaults
======================

.. data:: system_config_directory

   The pathname of the global (system wide) configuration directory used by
   `deb-pkg-tools` (a string).

   :default: The string ``/etc/deb-pkg-tools``.

.. data:: user_config_directory

   The pathname of the current user's configuration directory used by
   `deb-pkg-tools` (a string).

   :default: The expanded value of ``~/.deb-pkg-tools``.

.. data:: package_cache_file

   The pathname of the SQLite 3.x database containing the package cache
   used by :py:class:`.PackageCache()`.

   :default: The expanded value of ``~/.deb-pkg-tools/package-cache.sqlite3``.

.. data:: repo_config_file

   The base name of the configuration file containing user defined Debian
   package repositories (a string). This configuration file is loaded from
   :py:data:`system_config_directory` and/or :py:data:`user_config_directory`.

   :default: The string ``repos.ini``.
"""

# Standard library modules.
import os
import pwd

# We need these to pick the right locations.
user_id = os.getuid()
home_directory = pwd.getpwuid(user_id).pw_dir

# System wide locations.
system_config_directory = '/etc/deb-pkg-tools'
system_cache_directory = '/var/cache/deb-pkg-tools'

# User specific locations.
user_config_directory = os.path.join(home_directory, '.deb-pkg-tools')
user_cache_directory = os.path.join(home_directory, '.cache', 'deb-pkg-tools')

# The location of the package cache. If we're running as root we have write
# access to the system wide package cache so we'll pick that; the more users
# sharing this cache the more effective it is.
package_cache_directory = system_cache_directory if user_id == 0 else user_cache_directory
package_cache_file = os.path.join(package_cache_directory, 'package-cache.sqlite3')

# The filename of the repository configuration.
repo_config_file = 'repos.ini'

# vim: ts=4 sw=4 et
