# Debian packaging tools: Configuration defaults.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: June 1, 2014
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

   The pathname of the file containing the package cache used by
   :py:class:`deb_pkg_tools.repo.scan_packages()`.

   :default: The expanded value of ``~/.deb-pkg-tools/package-cache.json``.

.. data:: repo_config_file

   The base name of the configuration file containing user defined Debian
   package repositories (a string). This configuration file is loaded from
   :py:data:`system_config_directory` and/or :py:data:`user_config_directory`.

   :default: The string ``repos.ini``.
"""

# Standard library modules.
import os

# Modules included in our package.
from deb_pkg_tools.utils import find_home_directory

system_config_directory = '/etc/deb-pkg-tools'
user_config_directory = os.path.join(find_home_directory(), '.deb-pkg-tools')
package_cache_file = os.path.join(user_config_directory, 'package-cache.json')
repo_config_file = 'repos.ini'

# vim: ts=4 sw=4 et
