deb-pkg-tools: Debian packaging tools
=====================================

.. image:: https://travis-ci.org/xolox/python-deb-pkg-tools.svg?branch=master
   :target: https://travis-ci.org/xolox/python-deb-pkg-tools

.. image:: https://coveralls.io/repos/xolox/python-deb-pkg-tools/badge.png?branch=master
   :target: https://coveralls.io/r/xolox/python-deb-pkg-tools?branch=master

The Python package `deb-pkg-tools` is a collection of functions to build and
inspect `Debian binary packages`_ and repositories of binary packages. Its
primary use case is to automate builds.

Some of the functionality is exposed in the command line interface (documented below)
because it's very convenient to use in shell scripts, while other functionality
is meant to be used as a Python API. The package is currently tested on cPython
2.7, 3.5+ and PyPy (2.7).

Please note that `deb-pkg-tools` is quite opinionated about how Debian binary
packages should be built and it enforces some of these opinions on its users.
Most of this can be avoided with optional function arguments and/or environment
variables. If you find something that doesn't work to your liking and you can't
work around it, feel free to ask for an additional configuration option; I try
to keep an open mind about the possible use cases of my projects.

.. contents::

Status
------

On the one hand the `deb-pkg-tools` package is based on my experiences with
Debian packages and repositories over the past couple of years, on the other
hand `deb-pkg-tools` itself is quite young. Then again most functionality is
covered by automated tests; at the time of writing coverage is around 90% (some
of the error handling is quite tricky to test if we also want to test the
non-error case, which is of course the main focus :-)

Installation
------------

The `deb-pkg-tools` package is available on PyPI_ which means installation
should be as simple as:

.. code-block:: console

   $ pip install deb-pkg-tools

There's actually a multitude of ways to install Python packages (e.g. the `per
user site-packages directory`_, `virtual environments`_ or just installing
system wide) and I have no intention of getting into that discussion here, so
if this intimidates you then read up on your options before returning to these
instructions ;-).

When `deb-pkg-tools` is being used to scan thousands of ``*.deb`` archives a
significant speedup may be achieved using memcached:

.. code-block:: console

   $ pip install "deb-pkg-tools[memcached]"

Under the hood `deb-pkg-tools` uses several programs provided by Debian, the
details are available in the dependencies_ section. To install these programs:

.. code-block:: console

  $ sudo apt-get install dpkg-dev fakeroot lintian

Usage
-----

There are two ways to use the `deb-pkg-tools` package: As a command line
program and as a Python API. For details about the Python API please refer to
the API documentation available on `Read the Docs`_. The command line interface
is described below.

.. A DRY solution to avoid duplication of the `deb-pkg-tools --help' text:
..
.. [[[cog
.. from humanfriendly.usage import inject_usage
.. inject_usage('deb_pkg_tools.cli')
.. ]]]

**Usage:** `deb-pkg-tools [OPTIONS] ...`

Wrapper for the deb-pkg-tools Python project that implements various tools to
inspect, build and manipulate Debian binary package archives and related
entities like trivial repositories.

**Supported options:**

.. csv-table::
   :header: Option, Description
   :widths: 30, 70


   "``-i``, ``--inspect=FILE``","Inspect the metadata in the Debian binary package archive given by ``FILE``
   (similar to ""dpkg ``--info``"")."
   "``-c``, ``--collect=DIR``","Copy the package archive(s) given as positional arguments (and all package
   archives required by the given package archives) into the directory given
   by ``DIR``."
   "``-C``, ``--check=FILE``","Perform static analysis on a package archive and its dependencies in order
   to recognize common errors as soon as possible."
   "``-p``, ``--patch=FILE``","Patch fields into the existing control file given by ``FILE``. To be used
   together with the ``-s``, ``--set`` option."
   "``-s``, ``--set=LINE``","A line to patch into the control file (syntax: ""Name: Value""). To be used
   together with the ``-p``, ``--patch`` option."
   "``-b``, ``--build=DIR``","Build a Debian binary package with ""dpkg-deb ``--build``"" (and lots of
   intermediate Python magic, refer to the API documentation of the project
   for full details) based on the binary package template in the directory
   given by ``DIR``. The resulting archive is located in the system wide
   temporary directory (usually /tmp)."
   "``-u``, ``--update-repo=DIR``","Create or update the trivial Debian binary package repository in the
   directory given by ``DIR``."
   "``-a``, ``--activate-repo=DIR``","Enable ""apt-get"" to install packages from the trivial repository (requires
   root/sudo privilege) in the directory given by ``DIR``. Alternatively you can
   use the ``-w``, ``--with-repo`` option."
   "``-d``, ``--deactivate-repo=DIR``","Cleans up after ``--activate-repo`` (requires root/sudo privilege).
   Alternatively you can use the ``-w``, ``--with-repo`` option."
   "``-w``, ``--with-repo=DIR``","Create or update a trivial package repository, activate the repository, run
   the positional arguments as an external command (usually ""apt-get install"")
   and finally deactivate the repository."
   "``--gc``, ``--garbage-collect``","Force removal of stale entries from the persistent (on disk) package
   metadata cache. Garbage collection is performed automatically by the
   deb-pkg-tools command line interface when the last garbage collection
   cycle was more than 24 hours ago, so you only need to do it manually
   when you want to control when it happens (for example by a daily
   cron job scheduled during idle hours :-)."
   "``-y``, ``--yes``",Assume the answer to interactive questions is yes.
   "``-v``, ``--verbose``",Make more noise! (useful during debugging)
   "``-h``, ``--help``",Show this message and exit.

.. [[[end]]]

One thing to note is that the operation of ``deb-pkg-tools --update-repo`` can
be influenced by a configuration file. For details about this, please refer to
the documentation on `deb_pkg_tools.repo.select_gpg_key()`_.

.. _dependencies:

Dependencies
------------

The following external programs are required by `deb-pkg-tools` (depending on
which functionality you want to use of course):

=====================  =============
Program                Package
=====================  =============
``apt-ftparchive``     ``apt-utils``
``apt-get``            ``apt``
``cp``                 ``coreutils``
``dpkg-deb``           ``dpkg``
``dpkg-architecture``  ``dpkg-dev``
``du``                 ``coreutils``
``fakeroot``           ``fakeroot``
``gpg``                ``gnupg``
``gzip``               ``gzip``
``lintian``            ``lintian``
=====================  =============

The majority of these programs/packages will already be installed on most
Debian based systems so you should only need the following to get started:

.. code-block:: console

    $ sudo apt-get install dpkg-dev fakeroot lintian

Platform compatibility
----------------------

Several things can be tweaked via environment variables if they don't work for
your system or platform. For example on Mac OS X the ``cp`` command doesn't
have an ``-l`` parameter and the ``root`` user and group may not exist, but
despite these things it can still be useful to test package builds on Mac OS
X. The following environment variables can be used to adjust such factors:

.. csv-table::
   :header-rows: 1

   Environment variable,Default value
   `$DPT_ALLOW_FAKEROOT_OR_SUDO`_,true
   `$DPT_CHOWN_FILES`_,true
   `$DPT_FORCE_ENTROPY`_,false
   `$DPT_HARD_LINKS`_,true
   `$DPT_PARSE_STRICT`_,true
   `$DPT_RESET_SETGID`_,true
   `$DPT_ROOT_GROUP`_,root
   `$DPT_ROOT_USER`_,root
   `$DPT_SUDO`_,true

Environment variables for boolean options support the strings ``yes``,
``true``, ``1``, ``no``, ``false`` and ``0`` (case is ignored).

Disabling sudo usage
~~~~~~~~~~~~~~~~~~~~

To disable any use of ``sudo`` you can use the following:

.. code-block:: bash

   export DPT_ALLOW_FAKEROOT_OR_SUDO=false
   export DPT_CHOWN_FILES=false
   export DPT_RESET_SETGID=false
   export DPT_SUDO=false

Contact
-------

The latest version of `deb-pkg-tools` is available on PyPI_ and GitHub_. The
documentation is hosted on `Read the Docs`_. For bug reports please create an
issue on GitHub_. If you have questions, suggestions, etc. feel free to send me
an e-mail at `peter@peterodding.com`_.

License
-------

This software is licensed under the `MIT license`_.

© 2020 Peter Odding.

.. External references:
.. _deb_pkg_tools.repo.select_gpg_key(): https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.repo.select_gpg_key
.. _Debian binary packages: https://www.debian.org/doc/debian-policy/ch-binary.html
.. _$DPT_ALLOW_FAKEROOT_OR_SUDO: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.package.ALLOW_FAKEROOT_OR_SUDO
.. _$DPT_CHOWN_FILES: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.package.ALLOW_CHOWN
.. _$DPT_FORCE_ENTROPY: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.gpg.FORCE_ENTROPY
.. _$DPT_HARD_LINKS: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.package.ALLOW_HARD_LINKS
.. _$DPT_PARSE_STRICT: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.package.PARSE_STRICT
.. _$DPT_RESET_SETGID: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.package.ALLOW_RESET_SETGID
.. _$DPT_ROOT_GROUP: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.package.ROOT_GROUP
.. _$DPT_ROOT_USER: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.package.ROOT_USER
.. _$DPT_SUDO: https://deb-pkg-tools.readthedocs.io/en/latest/#deb_pkg_tools.repo.ALLOW_SUDO
.. _GitHub: https://github.com/xolox/python-deb-pkg-tools
.. _MIT license: http://en.wikipedia.org/wiki/MIT_License
.. _per user site-packages directory: https://www.python.org/dev/peps/pep-0370/
.. _peter@peterodding.com: peter@peterodding.com
.. _PyPI: https://pypi.python.org/pypi/deb-pkg-tools
.. _Read the Docs: https://deb-pkg-tools.readthedocs.io
.. _virtual environments: http://docs.python-guide.org/en/latest/dev/virtualenvs/
