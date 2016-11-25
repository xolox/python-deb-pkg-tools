.. include:: ../README.rst

Function reference
==================

The following documentation is based on the source code of version |release| of
the `deb-pkg-tools` package.

.. note:: Most of the functions defined by `deb-pkg-tools` depend on external
   programs. If these programs fail unexpectedly (end with a nonzero exit code)
   :exc:`executor.ExternalCommandFailed` is raised.

Package metadata cache
----------------------

.. automodule:: deb_pkg_tools.cache
   :members:

Static analysis of package archives
-----------------------------------

.. automodule:: deb_pkg_tools.checks
   :members:

Command line interface
----------------------

.. automodule:: deb_pkg_tools.cli
   :members:

Configuration defaults
----------------------

.. automodule:: deb_pkg_tools.config
   :members:

Control file manipulation
-------------------------

.. automodule:: deb_pkg_tools.control
   :members:

Relationship parsing and evaluation
-----------------------------------

.. automodule:: deb_pkg_tools.deps
   :members:

GPG key pair handling
---------------------

.. automodule:: deb_pkg_tools.gpg
   :members:

Package manipulation
--------------------

.. automodule:: deb_pkg_tools.package
   :members:

Repository management
---------------------

.. automodule:: deb_pkg_tools.repo
   :members:

Miscellaneous functions
-----------------------

.. automodule:: deb_pkg_tools.utils
   :members:

Version comparison
------------------

.. automodule:: deb_pkg_tools.version
   :members:
