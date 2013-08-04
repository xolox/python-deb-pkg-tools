deb-pkg-tools: Debian packaging tools
=====================================

The Python package `deb-pkg-tools` is a collection of functions to work with
Debian packages and repositories. Some of those functions have a command line
interface (see below) because they're very convenient to use in shell scripts,
while other functions are meant to be called directly from Python code.

Status
------

On the one hand the `deb-pkg-tools` package is based on my experiences with
Debian packages and repositories over the past couple of years, however on the
other hand `deb-pkg-tools` itself is quite young. However all functionality is
covered by automated tests; at the time of writing coverage is around 96% (some
of the error handling is quite tricky to test if we also want to test the
non-error case, which is of course the main focus :-)

Installation and usage
----------------------

You can install the `deb-pkg-tools` package using the following command::

    $ pip install deb-pkg-tools

After installation you'll have the ``deb-pkg-tools`` program available::

    $ deb-pkg-tools --help
    Usage: deb-pkg-tools [OPTIONS]

    Supported options:

      -i, --inspect=FILE         inspect the metadata in a *.deb archive
      -b, --build=DIR            build a Debian package with `dpkg-deb --build'
      -u, --update-repo=DIR      create/update a trivial package repository
      -a, --activate-repo=DIR    enable `apt-get' to install packages from a
                                 trivial repository (assumes root access)
      -d, --deactivate-repo=DIR  cleans up after --activate-repo
                                 (assumes root access)
      -v, --verbose              make more noise
      -h, --help                 show this message and exit

If you're interested in using `deb-pkg-tools` as a Python module, please refer
to the function reference on `Read the Docs`_.

Dependencies
------------

The `deb-pkg-tools` package depends on the python-debian_ package for control
file parsing. The following external programs are also required (depending on
which functionality you need of course):

=====================  =============
Program                Package
=====================  =============
``apt-ftparchive``     ``apt-utils``
``apt-get``            ``apt``
``ar``                 ``binutils``
``cat``                ``coreutils``
``cp``                 ``coreutils``
``dpkg-deb``           ``dpkg``
``dpkg-scanpackages``  ``dpkg-dev``
``du``                 ``coreutils``
``fakeroot``           ``fakeroot``
``gpg``                ``gnupg``
``gzip``               ``gzip``
``mv``                 ``coreutils``
``sed``                ``sed``
``tar``                ``tar``
=====================  =============

Contact
-------

The latest version of `deb-pkg-tools` is available on PyPI_ and GitHub_. The
documentation is hosted on `Read the Docs`_. For bug reports please create an
issue on GitHub_. If you have questions, suggestions, etc. feel free to send me
an e-mail at `peter@peterodding.com`_.

License
-------

This software is licensed under the `MIT license`_.

© 2013 Peter Odding.

.. External references:
.. _GitHub: https://github.com/xolox/python-deb-pkg-tools
.. _MIT license: http://en.wikipedia.org/wiki/MIT_License
.. _peter@peterodding.com: peter@peterodding.com
.. _PyPI: https://pypi.python.org/pypi/deb-pkg-tools
.. _python-debian: https://pypi.python.org/pypi/python-debian
.. _Read the Docs: https://deb-pkg-tools.readthedocs.org
