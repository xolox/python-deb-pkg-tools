deb-pkg-tools: Debian packaging tools
=====================================

.. image:: https://travis-ci.org/xolox/python-deb-pkg-tools.svg?branch=master
   :target: https://travis-ci.org/xolox/python-deb-pkg-tools

.. image:: https://coveralls.io/repos/xolox/python-deb-pkg-tools/badge.png?branch=master
   :target: https://coveralls.io/r/xolox/python-deb-pkg-tools?branch=master

The Python package `deb-pkg-tools` is a collection of functions to work with
Debian packages and repositories. Some of those functions have a command line
interface (see below) because they're very convenient to use in shell scripts,
while other functions are meant to be called directly from Python code. It's
currently tested on Python 2.6, 2.7 and 3.4.

Status
------

On the one hand the `deb-pkg-tools` package is based on my experiences with
Debian packages and repositories over the past couple of years, on the other
hand `deb-pkg-tools` itself is quite young. Then again most functionality is
covered by automated tests; at the time of writing coverage is around 90% (some
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

      -i, --inspect=FILE          inspect the metadata in a *.deb archive
      -b, --build=DIR             build a Debian package with `dpkg-deb --build'
      -u, --update-repo=DIR       create/update a trivial package repository
      -a, --activate-repo=DIR     enable `apt-get' to install packages from a
                                  trivial repository (requires root/sudo privilege)
      -d, --deactivate-repo=DIR   cleans up after --activate-repo
                                  (requires root/sudo privilege)
      -w, --with-repo=DIR CMD...  create/update a trivial package repository,
                                  activate the repository, run the positional
                                  arguments as an external command (usually `apt-get
                                  install') and finally deactivate the repository
      -v, --verbose               make more noise
      -h, --help                  show this message and exit

One thing to note is that the operation of ``deb-pkg-tools --update-repo`` can
be influenced by a configuration file. For details about this, please refer to
the documentation on `deb_pkg_tools.repo.select_gpg_key()`_.

If you're interested in using `deb-pkg-tools` as a Python module, please refer
to the function reference on `Read the Docs`_.

Dependencies
------------

The `deb-pkg-tools` package depends on the python-debian_ package for control
file parsing (it will be automatically installed as a dependency). The
following external programs are also required (depending on which functionality
you need of course):

=====================  =============
Program                Package
=====================  =============
``apt-ftparchive``     ``apt-utils``
``apt-get``            ``apt``
``ar``                 ``binutils``
``cp``                 ``coreutils``
``dpkg-deb``           ``dpkg``
``dpkg-scanpackages``  ``dpkg-dev``
``du``                 ``coreutils``
``fakeroot``           ``fakeroot``
``gpg``                ``gnupg``
``gzip``               ``gzip``
``lintian``            ``lintian``
``tar``                ``tar``
=====================  =============

The majority of these programs/packages will already be installed on most
Debian based systems so you should only need the following to get started::

    $ sudo apt-get install binutils dpkg-dev fakeroot lintian

Contact
-------

The latest version of `deb-pkg-tools` is available on PyPI_ and GitHub_. The
documentation is hosted on `Read the Docs`_. For bug reports please create an
issue on GitHub_. If you have questions, suggestions, etc. feel free to send me
an e-mail at `peter@peterodding.com`_.

License
-------

This software is licensed under the `MIT license`_.

© 2014 Peter Odding.

.. External references:
.. _deb_pkg_tools.repo.select_gpg_key(): https://deb-pkg-tools.readthedocs.org/en/latest/#deb_pkg_tools.repo.select_gpg_key
.. _GitHub: https://github.com/xolox/python-deb-pkg-tools
.. _MIT license: http://en.wikipedia.org/wiki/MIT_License
.. _peter@peterodding.com: peter@peterodding.com
.. _PyPI: https://pypi.python.org/pypi/deb-pkg-tools
.. _python-debian: https://pypi.python.org/pypi/python-debian
.. _Read the Docs: https://deb-pkg-tools.readthedocs.org
