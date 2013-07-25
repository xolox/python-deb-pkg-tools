.. include:: ../README.rst

Function reference
------------------

The following documentation is based on the source code of version |release| of
the `deb-pkg-tools` package.

.. note:: Most of the functions defined by `deb-pkg-tools` depend on external
   programs. If these programs fail unexpectedly (end with a nonzero exit code)
   :py:exc:`deb_pkg_tools.utils.ExternalCommandFailed` is raised.

.. automodule:: deb_pkg_tools.package
   :members:

.. automodule:: deb_pkg_tools.control
   :members:

.. automodule:: deb_pkg_tools.repo
   :members:

.. automodule:: deb_pkg_tools.utils
   :members:
