Changelog
=========

The purpose of this document is to list all of the notable changes to this
project. The format was inspired by `Keep a Changelog`_. This project adheres
to `semantic versioning`_.

.. contents::
   :local:

.. _Keep a Changelog: http://keepachangelog.com/
.. _semantic versioning: http://semver.org/

`Release 8.3`_ (2020-05-11)
---------------------------

Minor improvements to the :mod:`deb_pkg_tools.deb822` module:

**Slightly relax deb822 parsing**
 Leading and trailing comment blocks and empty lines that directly precede or
 follow a paragraph of control fields are now silently ignored. This is
 intended to improve compatibility with :pypi:`python-debian`.

**Improve deb822 parse errors**
 Shortly after I started using deb-pkg-tools 8.0 it became apparent that
 :func:`deb_pkg_tools.deb822.parse_deb822()` is quite a bit more strict than
 the previous usage of :pypi:`python-debian`. While I don't necessarily
 consider this a bad thing, it definitely highlighted a weak spot: The error
 messages didn't include filenames or line numbers. This is now fixed.

.. _Release 8.3: https://github.com/xolox/python-deb-pkg-tools/compare/8.2...8.3

`Release 8.2`_ (2020-05-02)
---------------------------

Removed :func:`textwrap.indent()` usage from :mod:`deb_pkg_tools.deb822` module
because this function isn't available on Python 2.7 which :pypi:`deb-pkg-tools`
still supports. Also added a regression test.

.. note:: While I definitely intend to drop Python 2 support in my open source
          projects at some point, right now is not the time for that just yet.

.. _Release 8.2: https://github.com/xolox/python-deb-pkg-tools/compare/8.1...8.2

`Release 8.1`_ (2020-04-25)
---------------------------

- Merged `pull request #22`_ which avoids a :exc:`~exceptions.ValueError`
  exception in the :func:`.inspect_package_contents()` function when a device
  file entry is parsed.

- Enhanced the :func:`.inspect_package_contents()` function to properly parse
  device file type information exposed via the new
  :attr:`.ArchiveEntry.device_type` attribute.

- Added a regression test for device file type parsing.

.. _Release 8.1: https://github.com/xolox/python-deb-pkg-tools/compare/8.0...8.1
.. _pull request #22: https://github.com/xolox/python-deb-pkg-tools/pull/22

`Release 8.0`_ (2020-04-25)
---------------------------

**Dropped GPL2 dependencies**
 The main purpose of this release was to resolve `issue #20`_ by dropping two
 GPL2 dependencies to avoid having to change the :pypi:`deb-pkg-tools` license
 from MIT to GPL2:

 python-apt_
  This dependency was previously used for Debian version comparison. This
  functionality has now been implemented in pure Python, for more details
  please refer to the new :mod:`deb_pkg_tools.version.native` module.

  .. note:: If this change introduces regressions for you, take a look at the
            :data:`deb_pkg_tools.version.PREFER_DPKG` variable, it may help as
            a temporary workaround. Also please report the regression 😇.

 :pypi:`python-debian`
  This dependency was previously used for Debian binary control file parsing.
  This functionality has now been implemented in pure Python, for more details
  please refer to the new :mod:`deb_pkg_tools.deb822` module.

**Updated Python compatibility**
 Python 3.8 is now officially supported, 3.4 is no longer supported.

**Fixed deprecation warnings**
 Fixed :pypi:`humanfriendly` 8.0 deprecation warnings and bumped requirements I
 authored that went through the same process. Also defined the first
 deprecated aliases in the :pypi:`deb-pkg-tools` code base (in the process of
 implementing the functionality required to drop the GPL2 dependencies).

**Quality boost for deb_pkg_tools.control module**
 The :mod:`deb_pkg_tools.control` module saw a lot of small changes to make the
 handling of case insensitivity and byte strings versus Unicode strings more
 consistent. The most important changes:

 - All functions that return dictionaries now return the same type of case
   insensitive dictionaries (see :class:`~deb_pkg_tools.deb822.Deb822`).

 - The complete module now expects and uses Unicode strings internally.
   Character encoding and decoding is only done when control files are
   read from and written to disk.

.. _Release 8.0: https://github.com/xolox/python-deb-pkg-tools/compare/7.0...8.0
.. _issue #20: https://github.com/xolox/python-deb-pkg-tools/issues/20

`Release 7.0`_ (2020-02-07)
---------------------------

**Code changes:**

- Make :func:`~deb_pkg_tools.package.update_conffiles()` optional (requested in
  `#19`_) in the Python API.

- Make :func:`~deb_pkg_tools.package.find_object_files()` use a builtin exclude
  list of filename patterns to ignore.

- Start using ``__all__`` to control what is exported:

  - This change is backwards incompatible in the sense that until now imports
    were exposed to the outside world, however for anyone to actually use this
    would imply not having read the documentation, so this doesn't really
    bother me.

  - In theory this change could be backwards incompatible in a bad way if I
    omitted ``__all__`` entries that should have been exported. I did double
    check but of course I can't be 100% sure (the ``deb_pkg_tools.*`` modules
    currently span almost 6000 lines including whitespace and comments).

  - I decided to bump the major version number because of the potential for
    import errors caused by the introduction of ``__all__``.

**Documentation updates:**

- Simplified the overview of environment variables in the readme by properly
  documenting individual options and linking to their documentation entries.
  Over the years I've picked up the habit of treating my documentation just
  like my code: Make sure everything is defined in a single place (DRY), as
  close as possible to the place where it is used. Properly documenting all of
  the module variables that are based on environment variables and linking to
  those from the readme frees me from the burden of explaining things in more
  than one place. This is good because multiple explanations increase the
  chance of documentation becoming outdated or contradictoring itself, which
  are definitely problems to be avoided whenever possible.
- Started using ``:man:`` role to link to Linux manual pages.
- Changed Read the Docs URL (``s/\.org$/.io/g``).

**Documented variables:**

.. csv-table::
   :header-rows: 1

   Module variable,Environment variable
   :data:`deb_pkg_tools.gpg.FORCE_ENTROPY`,``$DPT_FORCE_ENTROPY``
   :data:`deb_pkg_tools.package.ALLOW_CHOWN`,``$DPT_CHOWN_FILES``
   :data:`deb_pkg_tools.package.ALLOW_FAKEROOT_OR_SUDO`,``$DPT_ALLOW_FAKEROOT_OR_SUDO``
   :data:`deb_pkg_tools.package.ALLOW_HARD_LINKS`,``$DPT_HARD_LINKS``
   :data:`deb_pkg_tools.package.ALLOW_RESET_SETGID`,``$DPT_RESET_SETGID``
   :data:`deb_pkg_tools.package.BINARY_PACKAGE_ARCHIVE_EXTENSIONS`
   :data:`deb_pkg_tools.package.DEPENDENCY_FIELDS`
   :data:`deb_pkg_tools.package.DIRECTORIES_TO_REMOVE`
   :data:`deb_pkg_tools.package.FILES_TO_REMOVE`
   :data:`deb_pkg_tools.package.PARSE_STRICT`,``$DPT_PARSE_STRICT``
   :data:`deb_pkg_tools.package.ROOT_GROUP`,``$DPT_ROOT_GROUP``
   :data:`deb_pkg_tools.package.ROOT_USER`,``$DPT_ROOT_USER``
   :data:`deb_pkg_tools.repo.ALLOW_SUDO`,``$DPT_SUDO``

.. _Release 7.0: https://github.com/xolox/python-deb-pkg-tools/compare/6.1...7.0
.. _#19: https://github.com/xolox/python-deb-pkg-tools/issues/19

`Release 6.1`_ (2020-02-05)
---------------------------

Implemented a feature requested from me via private email:

**Problem:** When filename parsing of ``*.deb`` archives fails to recognize a
package name, version and architecture encoded in the filename (delimited by
underscores) then deb-pkg-tools reports an error and aborts:

.. code-block:: none

   ValueError: Filename doesn't have three underscore separated components!

**Solution:** Setting the environment variable ``$DPT_PARSE_STRICT`` to
``false`` changes this behavior so that the required information is extracted
from the package metadata instead of reporting an error.

For now the default remains the same (an error is reported) due to backwards
compatibility and the principle of least surprise (for those who previously
integrated deb-pkg-tools). This will likely change in the future.

**Miscellaneous changes:**

- Use 'console' highlighting in readme (prompt are now highlighted).
- Added license=MIT to ``setup.py`` script.
- Bumped copyright to 2020.

.. _Release 6.1: https://github.com/xolox/python-deb-pkg-tools/compare/6.0...6.1

`Release 6.0`_ (2019-09-13)
---------------------------

- Enable compatibility with newer python-apt_ releases:

  - The test suite has been modified to break on Travis CI when python-apt_
    should be available but isn't (when the Python virtual environment is based
    on a Python interpreter provided by Ubuntu, currently this applies to all
    build environments except Python 3.7).

  - The idea behind the test suite change is to verify that the conditional
    import chain in ``version.py`` always succeeds (on Travis CI, where I
    control the runtime environment).

  - This was added when after much debugging I finally realized why the new
    Ubuntu 18.04 build server I'd created was so awfully slow: The conditional
    import chain had been "silently broken" without me realizing it, except for
    the fact that using the fall back implementation based on ``dpkg
    --compare-versions`` to sort through thousands of version numbers was
    rather noticeably slow... 😇

- Make python-memcached_ an optional dependency in response to `#13`_.

- Dropped Python 2.6 compatibility.

.. _Release 6.0: https://github.com/xolox/python-deb-pkg-tools/compare/5.2...6.0
.. _python-memcached: https://pypi.org/project/python-memcached
.. _#13: https://github.com/xolox/python-deb-pkg-tools/issues/13

`Release 5.2`_ (2018-11-17)
---------------------------

Promote python-debian version constraint into a conditional dependency.

Recently I constrained the version of python-debian to work around a Python 2.6
incompatibility. This same incompatibility is now biting me in the `py2deb
setup on Travis CI`_ and after fighting that situation for a while I decided it
may be better (less convoluted) to fix this in deb-pkg-tools instead (at the
source of the problem, so to speak).

.. _Release 5.2: https://github.com/xolox/python-deb-pkg-tools/compare/5.1.1...5.2
.. _py2deb setup on Travis CI: https://github.com/paylogic/py2deb/compare/4284a1db99699bab14bc5fb62a88256a5d1ae978...60ece9ffebbd5f1bdff7ea20fbf0eeb401a9da3f

`Release 5.1.1`_ (2018-10-26)
-----------------------------

Bug fix for logic behind ``deb_pkg_tools.GPGKey.existing_files`` property: The
configured ``directory`` wasn't being scanned in combination with GnuPG < 2.1
even though the use of ``directory`` has become the preferred way to configure
GnuPG < 2.1 as well as GnuPG >= 2.1 (due to the GnuPG bug mentioned in the
release notes of release 5.1).

.. _Release 5.1.1: https://github.com/xolox/python-deb-pkg-tools/compare/5.1...5.1.1

`Release 5.1`_ (2018-10-26)
---------------------------

Added the ``deb_pkg_tools.gpg.GPGKey.identifier`` property that uses the ``gpg
--list-keys --with-colons`` command to introspect the key pair and extract a
unique identifier:

- When a fingerprint is available in the output this is the preferred value.
- Otherwise the output is searched for a key ID.

If neither of these values is available an exception is raised.

.. note:: While testing this I noticed that the old style ``gpg
          --no-default-keyring --keyring=… --secret-keyring=…`` commands don't
          support the ``--list-keys`` command line option. The only workaround
          for this is to use the ``directory`` property (which triggers the use
          of ``--homedir``) instead of the ``public_key_file`` and
          ``secret_key_file`` properties. This appears to be due to a bug in
          older GnuPG releases (see `this mailing list thread`_).

.. _Release 5.1: https://github.com/xolox/python-deb-pkg-tools/compare/5.0...5.1
.. _this mailing list thread: https://lists.gnupg.org/pipermail/gnupg-users/2002-March/012144.html

`Release 5.0`_ (2018-10-25)
---------------------------

**GnuPG >= 2.1 compatibility for repository signing.**

This release became rather more involved than I had hoped it would 😇 because
of backwards incompatibilities in GnuPG >= 2.1 that necessitated changes in the
API that deb-pkg-tools presents to its users:

- The ``--secret-keyring`` option has been obsoleted and is ignored and
  the suggested alternative is the use of an `ephemeral home directory`_ which
  changes how a key pair is specified.

- This impacts the API of the ``deb_pkg_tools.gpg.GPGKey`` class as well as
  the ``repos.ini`` support in ``deb_pkg_tools.repo.update_repository()``.

The documentation has been updated to explain all of this, refer to the
``deb_pkg_tools.gpg`` module for details. Detailed overview of changes:

- The ``deb_pkg_tools.gpg.GPGKey`` class is now based on ``property-manager``
  and no longer uses instance variables, because this made it easier for
  me to split up the huge ``__init__()`` method into manageable chunks.

  A side effect is that ``__init__()`` no longer supports positional
  arguments which technically speaking is **backwards incompatible**
  (although I never specifically intended it to be used like that).

- The ``deb_pkg_tools.gpg.GPGKey`` class now raises an exception when it
  detects that the use of an isolated key pair is intended but the
  ``directory`` option has not been provided even though GnuPG >= 2.1 is
  being used. While this exception is new, the previous behavior on
  GnuPG >= 2.1 was anything but sane, so any thoughts about the
  backwards compatibility of this new exception are a moot point.

- The ``deb_pkg_tools.gpg.GPGKey`` used to raise ``TypeError`` when a key pair
  is explicitly specified but only one of the two expected files exists, in
  order to avoid overwriting files not "owned" by deb-pkg-tools. An exception
  is still raised but the type has been changed to ``EnvironmentError`` because
  I felt that it was more appropriate. This is technically **backwards
  incompatible** but I'd be surprised if this affects even a single user...

- The repository activation fall back test (that generates an automatic
  signing key in order to generate ``Release.gpg``) was failing for me on
  Ubuntu 18.04 and in the process of debugging this I added support for
  ``InRelease`` files. In the end this turned out to be irrelevant to the
  issue at hand, but I saw no harm in keeping the ``InRelease`` support.
  This is under the assumption that the presence of an ``InRelease`` file
  shouldn't disturb older ``apt-get`` versions (which seems like a sane
  assumption to me - it's just a file on a webserver, right?).

- Eventually I found out that the repository activation fall back test
  was failing due to the key type of the automatic signing key that's
  generated during the test: As soon as I changed that from DSA to RSA
  things started working.

- GnuPG profile directory initialization now applies 0700 permissions to
  avoid noisy warnings from GnuPG.

- Added Python 3.7 to tested and and supported versions.

- Improved ``update_repository()`` documentation.

- Moved function result caching to ``humanfriendly.decorators``.

- I've changed ``Depends`` to ``Recommends`` in ``stdeb.cfg``, with the
  following rationale:

  - The deb-pkg-tools package provides a lot of loosely related functionality
    depending on various external commands. For example building of Debian
    binary packages requires quite a few programs to be installed.

  - But not every use case of deb-pkg-tools requires all of these external
    commands, so demanding that they always be installed is rather inflexible.

  - In my specific case this dependency creep blocked me from building
    lightweight tools on top of deb-pkg-tools, because the dependency chain
    would pull in a complete build environment. That was more than I bargained
    for when I wanted to use a few utility functions in deb-pkg-tools 😅.

  - With this change, users are responsible for installing the appropriate
    packages. But then I estimate that less than one percent of my users are
    actually affected by this change, because of the low popularity of
    solutions like stdeb_ and py2deb_ 😇.

  - Only the python-apt_ package remains as a strict dependency instead of a
    recommended dependency, see 757286fc8ce_ for the rationale.

- Removed python-apt_ intersphinx reference (`for now
  <https://bugs.launchpad.net/ubuntu/+source/python-apt/+bug/1799807>`_).

- Added this changelog to the repository and documentation.

.. _Release 5.0: https://github.com/xolox/python-deb-pkg-tools/compare/4.5...5.0
.. _stdeb: https://pypi.org/project/stdeb/
.. _ephemeral home directory: https://www.gnupg.org/documentation/manuals/gnupg/Ephemeral-home-directories.html#Ephemeral-home-directories
.. _757286fc8ce: https://github.com/xolox/python-deb-pkg-tools/commit/757286fc8ce
.. _python-apt: https://packages.debian.org/python-apt

`Release 4.5`_ (2018-02-25)
---------------------------

Improved robustness of ``dpkg-shlibdeps`` and ``strip`` integration (followup
to `release 4.4`_).

.. _Release 4.5: https://github.com/xolox/python-deb-pkg-tools/compare/4.4...4.5

`Release 4.4`_ (2018-02-25)
---------------------------

Integrated support for ``dpkg-shlibdeps`` (inspired by py2deb_).

I first started (ab)using ``dpkg-shlibdeps`` in the py2deb_ project and have
since missed this functionality in other projects like deb-pkg-tools so have
decided to move some stuff around :-).

.. _Release 4.4: https://github.com/xolox/python-deb-pkg-tools/compare/4.3...4.4
.. _py2deb: https://github.com/paylogic/py2deb

`Release 4.3`_ (2018-02-25)
---------------------------

- Make mandatory control field validation reusable.
- Include documentation in source distributions.
- Restore Python 2.6 compatibility in test suite.

.. _Release 4.3: https://github.com/xolox/python-deb-pkg-tools/compare/4.2...4.3

`Release 4.2`_ (2017-07-10)
---------------------------

Implement cache invalidation (follow up to `#12`_).

.. _Release 4.2: https://github.com/xolox/python-deb-pkg-tools/compare/4.1...4.2

`Release 4.1`_ (2017-07-10)
---------------------------

- Merged pull request `#11`_: State purpose of project in readme.
- Improve dependency parsing: Add more ``Depends`` like fields (fixes `#12`_).
- Start using ``humanfriendly.testing`` to mark skipped tests.
- Changed Sphinx documentation theme.
- Add Python 3.6 to tested versions.

.. _Release 4.1: https://github.com/xolox/python-deb-pkg-tools/compare/4.0.2...4.1
.. _#11: https://github.com/xolox/python-deb-pkg-tools/pull/11
.. _#12: https://github.com/xolox/python-deb-pkg-tools/issues/12

`Release 4.0.2`_ (2017-02-02)
-----------------------------

Bug fix for inheritance of ``AlternativeRelationship``. This fixes the
following error when hashing relationship objects::

  AttributeError: 'AlternativeRelationship' object has no attribute 'operator'

I'd like to add tests for this but lack the time to do so at this moment,
so hopefully I can revisit this later when I have a bit more time 😇.

.. _Release 4.0.2: https://github.com/xolox/python-deb-pkg-tools/compare/4.0.1...4.0.2

`Release 4.0.1`_ (2017-02-01)
-----------------------------

- Bug fix: Swallow unpickling errors instead of propagating them.

  In general I am very much opposed to Python code that swallows exceptions
  when it doesn't know how to handle them, because it can inadvertently obscure
  an issue's root cause and/or exacerbate the issue.

  But caching deserves an exception. Any code that exists solely as an
  optimization should not raise exceptions caused by the caching logic. This
  should avoid the following traceback which I just ran into::

    Traceback (most recent call last):
      File ".../lib/python2.7/site-packages/deb_pkg_tools/cli.py", line 382, in with_repository_wrapper
        with_repository(directory, \*command, cache=cache)
      File ".../lib/python2.7/site-packages/deb_pkg_tools/repo.py", line 366, in with_repository
        cache=kw.get('cache'))
      File ".../lib/python2.7/site-packages/deb_pkg_tools/repo.py", line 228, in update_repository
        cache=cache)
      File ".../lib/python2.7/site-packages/deb_pkg_tools/repo.py", line 91, in scan_packages
        fields = dict(inspect_package_fields(archive, cache=cache))
      File ".../lib/python2.7/site-packages/deb_pkg_tools/package.py", line 480, in inspect_package_fields
        value = entry.get_value()
      File ".../lib/python2.7/site-packages/deb_pkg_tools/cache.py", line 268, in get_value
        from_fs = pickle.load(handle)
    ValueError: unsupported pickle protocol: 3

- Added ``property-manager`` to intersphinx mapping (enabling links in the online documentation).

.. _Release 4.0.1: https://github.com/xolox/python-deb-pkg-tools/compare/4.0...4.0.1

`Release 4.0`_ (2017-01-31)
---------------------------

- **Added support for parsing of architecture restrictions** (`#9`_).

- Switched ``deb_pkg_tools.deps`` to use ``property-manager`` and removed
  ``cached-property`` requirement in the process:

  - This change simplified the deb-pkg-tools code base by removing the
    ``deb_pkg_tools.compat.total_ordering`` and
    ``deb_pkg_tools.utils.OrderedObject`` classes.

  - The introduction of ``property-manager`` made it easier for me to
    extend ``deb_pkg_tools.deps`` with the changes required to support
    'architecture restrictions' (issue `#9`_).

- Add ``Build-Depends`` to ``DEPENDS_LIKE_FIELDS``. I noticed while testing
  with the example provided in issue `#9`_ that the dependencies in the
  ``Build-Depends`` field weren't being parsed. Given that I was working on
  adding support for parsing of architecture restrictions (as suggested in
  issue `#9`_) this seemed like a good time to fix this 🙂.

- Updated ``generate_stdeb_cfg()``.

**About backwards compatibility:**

I'm bumping the major version number because 754debc0b61_ removed the
``deb_pkg_tools.compat.total_ordering`` and ``deb_pkg_tools.utils.OrderedObject``
classes and internal methods like ``_key()`` so strictly speaking this breaks
backwards compatibility, however both of these classes were part of
miscellaneous scaffolding used by deb-pkg-tools but not an intentional part of
the documented API, so I don't expect this to be particularly relevant to most
(if not all) users of deb-pkg-tools.

.. _Release 4.0: https://github.com/xolox/python-deb-pkg-tools/compare/3.1...4.0
.. _#9: ttps://github.com/xolox/python-deb-pkg-tools/issues/9
.. _754debc0b61: https://github.com/xolox/python-deb-pkg-tools/commit/754debc0b61

`Release 3.1`_ (2017-01-27)
---------------------------

- Merged pull request `#8`_: Add support for ``*.udeb`` micro packages.
- Updated test suite after merging `#8`_.
- Suggest memcached in ``stdeb.cfg``.
- Added ``readme`` target to ``Makefile``.

.. _Release 3.1: https://github.com/xolox/python-deb-pkg-tools/compare/3.0...3.1
.. _#8: ttps://github.com/xolox/python-deb-pkg-tools/pull/8

`Release 3.0`_ (2016-11-25)
---------------------------

This release was a huge refactoring to enable concurrent related package
collection. In the process I switched from SQLite to the Linux file system
(augmented by memcached) because SQLite completely collapsed under concurrent
write activity (it would crap out consistently beyond a certain number of
concurrent readers and writers).

Detailed changes:

- Refactored makefile, setup script, Travis CI configuration, etc.
- Bug fix: Don't unnecessarily garbage collect cache.
- Experimented with increased concurrency using SQLite Write-Ahead Log (WAL).
- Remove redundant :py: prefixes from RST references
- Fix broken RST references logged by ``sphinx-build -n``.
- Moved ``deb_pkg_tools.utils.compact()`` to ``humanfriendly.text.compact()``.
- Fixed a broken pretty printer test.
- Implement and enforce PEP-8 and PEP-257 compliance
- Switch from SQLite to filesystem for package cache (to improve concurrency
  between readers and writers). The WAL did not improve things as much as I
  would have hoped...
- Document and optimize filesystem based package metadata cache
- Add some concurrency to ``deb-pkg-tools --collect`` (when more than one
  archive is given, the collection of related archives is performed
  concurrently for each archive given).
- Re-implement garbage collection for filesystem based cache.
- Improvements to interactive package collection:

  - Don't use multiprocessing when a single archive is given because it's kind
    of silly to fork subprocesses for no purpose at all.

  - Restored the functionality of the optional 'cache' argument because the new
    in memory / memcached / filesystem based cache is so simple it can be
    passed to multiprocessing workers.

- Enable manual garbage collection (``deb-pkg-tools --garbage-collect``).
- Updated usage in readme.
- Improvements to interactive package collection:

  - A single spinner is rendered during concurrent collection (instead of
    multiple overlapping spinners that may not be synchronized).

  - The order of the ``--collect`` and ``--yes`` options no longer matters.

  - When the interactive spinner is drawn it will always be cleared, even if
    the operator presses Control-C (previously it was possible for the text
    cursor to remain hidden after ``deb-pkg-tools --collect`` was interrupted
    by Control-C).

- Include command line interface in documentation.

.. _Release 3.0: https://github.com/xolox/python-deb-pkg-tools/compare/2.0...3.0

`Release 2.0`_ (2016-11-18)
---------------------------

Stop using the system wide temporary directory in order to enable concurrent builds.

.. _Release 2.0: https://github.com/xolox/python-deb-pkg-tools/compare/1.37...2.0

`Release 1.37`_ (2016-11-17)
----------------------------

Significant changes:

- Prefer hard linking over copying of package archives from one directory to another.

- Change Unicode output handling in command line interface. This revisits the
  'hack' that I implemented in bc9b52419ea_ because I noticed today (after
  integrating ``humanfriendly.prompts.prompt_for_confirmation()``) that the
  wrapping of ``sys.stdout`` disables libreadline support in interactive
  prompts (``input()`` and ``raw_input()``) which means readline hints are
  printed to stdout instead of being interpreted by libreadline, making
  interactive prompts rather hard to read :-s.

Miscellaneous changes:

- Test Python 3.5 on Travis CI.
- Don't test tags on Travis CI.
- Use ``pip`` instead of ``python setup.py install`` on Travis CI.
- Uncovered and fixed a Python 3 incompatibility in the test suite.

.. _Release 1.37: https://github.com/xolox/python-deb-pkg-tools/compare/1.36...1.37
.. _bc9b52419ea: https://github.com/xolox/python-deb-pkg-tools/commit/bc9b52419ea

`Release 1.36`_ (2016-05-04)
----------------------------

Make it possible to integrate with GPG agent (``$GPG_AGENT_INFO``).

.. _Release 1.36: https://github.com/xolox/python-deb-pkg-tools/compare/1.35...1.36

`Release 1.35`_ (2015-09-24)
----------------------------

Include ``Breaks`` in control fields parsed like ``Depends``.

.. _Release 1.35: https://github.com/xolox/python-deb-pkg-tools/compare/1.34.1...1.35

`Release 1.34.1`_ (2015-09-07)
------------------------------

Bug fix: Invalidate old package metadata caches (from before version 1.31.1).

Should have realized this much sooner of course but I didn't, for which my
apologies if this bit anyone like it bit me 😇. I wasted two hours trying to
find out why something that was logically impossible (judging by the code base)
was happening anyway. Cached data in the old format! 😒

.. _Release 1.34.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.34...1.34.1

`Release 1.34`_ (2015-07-16)
----------------------------

Automatically embed usage in readme (easier to keep up to date 😇).

.. _Release 1.34: https://github.com/xolox/python-deb-pkg-tools/compare/1.33...1.34

`Release 1.33`_ (2015-07-16)
----------------------------

Added ``deb_pkg_tools.control.create_control_file()`` function.

.. _Release 1.33: https://github.com/xolox/python-deb-pkg-tools/compare/1.32.2...1.33

`Release 1.32.2`_ (2015-05-01)
------------------------------

Bug fixes for related package archive collection.

.. _Release 1.32.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.32.1...1.32.2

`Release 1.32.1`_ (2015-05-01)
------------------------------

- Include ``Pre-Depends`` in control fields parsed like ``Depends:``.
- Updated doctest examples with regards to changes in bebe413dcc5_.
- Improved documentation of ``parse_filename()``.

.. _Release 1.32.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.32...1.32.1
.. _bebe413dcc5: https://github.com/xolox/python-deb-pkg-tools/commit/bebe413dcc5

`Release 1.32`_ (2015-04-23)
----------------------------

Improve implementation and documentation of ``collect_related_packages()``.

The result of the old implementation was dependent on the order of entries
returned from ``os.listdir()`` which can differ from system to system (say my
laptop vervsus Travis CI) and so caused inconsistently failing builds.

.. _Release 1.32: https://github.com/xolox/python-deb-pkg-tools/compare/1.31...1.32

`Release 1.31`_ (2015-04-11)
----------------------------

- Extracted installed version discovery to re-usable function.
- ``dpkg-scanpackages`` isn't used anymore, remove irrelevant references.

.. _Release 1.31: https://github.com/xolox/python-deb-pkg-tools/compare/1.30...1.31

`Release 1.30`_ (2015-03-18)
----------------------------

Added ``deb_pkg_tools.utils.find_debian_architecture()`` function.

This function is currently not used by deb-pkg-tools itself but several of my
projects that build on top of deb-pkg-tools need this functionality and all of
them eventually got their own implementation. I've now decided to implement
this once, properly, so that all projects can use the same tested and properly
documented implementation (as simple as it may be).

.. _Release 1.30: https://github.com/xolox/python-deb-pkg-tools/compare/1.29.4...1.30

`Release 1.29.4`_ (2015-02-26)
------------------------------

Adapted pull request `#5`_ to restore Python 3 compatibility.

.. _Release 1.29.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.29.3...1.29.4
.. _#5: ttps://github.com/xolox/python-deb-pkg-tools/pull/5

`Release 1.29.3`_ (2014-12-16)
------------------------------

Changed SQLite row factory to "restore" Python 3.4.2 compatibility.

The last Travis CI builds that ran on Python 3.4.1 worked fine and no changes
were made in deb-pkg-tools since then so this is clearly caused by a change in
Python's standard library. This is an ugly workaround but it's the most elegant
way I could find to "restore" compatibility.

.. _Release 1.29.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.29.2...1.29.3

`Release 1.29.2`_ (2014-12-16)
------------------------------

Bug fix: Don't normalize ``Depends:`` lines.

Apparently ``dpkg-scanpackages`` and compatible re-implementations like the one
in deb-pkg-tools should not normalize ``Depends:`` fields because apt can get
confused by this. Somehow it uses either a literal comparison of the metadata
or a comparison of the hash of the metadata to check if an updated package is
available (I tried to find this in the apt sources but failed to do so due to
my limited experience with C++). So when the ``Depends:`` line in the
``Packages.gz`` file differs from the ``Depends:`` line in the binary control
file inside a ``*.deb`` apt will continuously re-download and install the same
binary package...

.. _Release 1.29.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.29.1...1.29.2

`Release 1.29.1`_ (2014-11-15)
------------------------------

Moved ``coerce_boolean()`` to humanfriendly package.

.. _Release 1.29.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.29...1.29.1

`Release 1.29`_ (2014-10-19)
----------------------------

Merged pull request `#4`_: Added ``$DPT_ALLOW_FAKEROOT_OR_SUDO`` and
``$DPT_CHOWN_FILES`` environment variables to make ``sudo`` optional.

.. _Release 1.29: https://github.com/xolox/python-deb-pkg-tools/compare/1.28...1.29
.. _#4: ttps://github.com/xolox/python-deb-pkg-tools/pull/4

`Release 1.28`_ (2014-09-17)
----------------------------

Change location of package cache when ``os.getuid() == 0``.

.. _Release 1.28: https://github.com/xolox/python-deb-pkg-tools/compare/1.27.3...1.28

`Release 1.27.3`_ (2014-08-31)
------------------------------

Sanitize permissions of ``DEBIAN/{pre,post}{inst,rm}`` and ``etc/sudoers.d/*``.

.. _Release 1.27.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.27.2...1.27.3

`Release 1.27.2`_ (2014-08-31)
------------------------------

Improve Python 2.x/3.x compatibility (return lists explicitly).

.. _Release 1.27.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.27.1...1.27.2

`Release 1.27.1`_ (2014-08-31)
------------------------------

- Bug fix for SQLite cache string encoding/decoding on Python 3.x.
- Bug fix for check_package() on Python 3.x.
- Bug fix for obscure Python 3.x issue (caused by mutating a list while iterating it).
- Make collect_related_packages() a bit faster (actually quite a lot when
  ``dpkg --compare-versions`` is being used 🙂).
- Make ``deb_pkg_tools.control.*`` less verbose.

.. _Release 1.27.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.27...1.27.1

`Release 1.27`_ (2014-08-31)
----------------------------

- Added command line interface for static checks (with improved test coverage).
- Made ``collect_related_packages()`` a bit faster.
- "Refine" entry collection strategy for Travis CI.

.. _Release 1.27: https://github.com/xolox/python-deb-pkg-tools/compare/1.26.4...1.27

`Release 1.26.4`_ (2014-08-30)
------------------------------

Restore Python 3.x compatibility (`failing build
<https://travis-ci.org/xolox/python-deb-pkg-tools/jobs/33995580>`_).

.. _Release 1.26.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.26.3...1.26.4

`Release 1.26.3`_ (2014-08-30)
------------------------------

Still not enough entropy on Travis CI, let's see if we can work around that...

I tried to fix this using ``rng-tools`` in 3c372c3097f_ but that didn't work
out due to the way OpenVZ works. This commit introduces a more general approach
that will hopefully work on OpenVZ and other virtualized environments, we'll
see...

.. _Release 1.26.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.26.2...1.26.3
.. _3c372c3097f: https://github.com/xolox/python-deb-pkg-tools/commit/3c372c3097f

`Release 1.26.2`_ (2014-08-30)
------------------------------

- Restore Python 3 compatibility.
- Improve test coverage.
- Try to work around lack of entropy on Travis CI.

.. _Release 1.26.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.26...1.26.2

`Release 1.26`_ (2014-08-30)
----------------------------

Add static analysis to detect version conflicts.

.. _Release 1.26: https://github.com/xolox/python-deb-pkg-tools/compare/1.25...1.26

`Release 1.25`_ (2014-08-30)
----------------------------

Make ``collect_related_packages()`` 5x faster:

- Use high performance decorator to memoize overrides of ``Relationship.matches()``.
- Exclude conflicting packages from all further processing as soon as they are found.
- Moved the dpkg comparison cache around.
- Removed ``Version.__hash__()``.

.. _Release 1.25: https://github.com/xolox/python-deb-pkg-tools/compare/1.24.1...1.25

`Release 1.24.1`_ (2014-08-26)
------------------------------

Bug fix for unused parameter in 442d67cf4dd_.

.. _Release 1.24.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.24...1.24.1
.. _442d67cf4dd: https://github.com/xolox/python-deb-pkg-tools/commit/442d67cf4dd

`Release 1.24`_ (2014-08-26)
----------------------------

Normalize setgid bits (because ``dpkg-deb`` doesn't like them).

.. _Release 1.24: https://github.com/xolox/python-deb-pkg-tools/compare/1.23.4...1.24

`Release 1.23.4`_ (2014-08-04)
------------------------------

Merged pull request `#2`_: Improve platform compatibility with environment variables.

- Added user-name and user-group overrides (``$DPT_ROOT_USER``,
  ``$DPT_ROOT_GROUP``) for systems that don't have a ``root`` group or when
  ``root`` isn't a desirable consideration when building packages.

- Can now disable hard-links (``$DPT_HARD_LINKS``). The ``cp -l`` parameter is
  not supported on Mavericks 10.9.2.

- Replaced ``du -sB`` with ``du -sk`` (not supported on Mavericks 10.9.2).

- Can now disable ``sudo`` (``$DPT_SUDO``) since it's sometimes not desirable
  and not required just to build the package (for example on MacOS, refer to
  pull request `#2`_ for an actual use case).

.. _Release 1.23.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.23.3...1.23.4
.. _#2: ttps://github.com/xolox/python-deb-pkg-tools/pull/2

`Release 1.23.3`_ (2014-06-27)
------------------------------

Bug fix for ``copy_package_files()``.

.. _Release 1.23.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.23.2...1.23.3

`Release 1.23.2`_ (2014-06-25)
------------------------------

Further improvements to ``collect_packages()``.

.. _Release 1.23.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.23.1...1.23.2

`Release 1.23.1`_ (2014-06-25)
------------------------------

Bug fix: Don't swallow keyboard interrupt in ``collect_packages()`` wrapper.

.. _Release 1.23.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.23...1.23.1

`Release 1.23`_ (2014-06-25)
----------------------------

Added ``group_by_latest_versions()`` function.

.. _Release 1.23: https://github.com/xolox/python-deb-pkg-tools/compare/1.22.6...1.23

`Release 1.22.6`_ (2014-06-22)
------------------------------

Try to fix cache deserialization errors on older platforms (refer to the commit
message of 8b04dfcd4d3_ for more details about the errors I'm talking about).

.. _Release 1.22.6: https://github.com/xolox/python-deb-pkg-tools/compare/1.22.5...1.22.6
.. _8b04dfcd4d3: https://github.com/xolox/python-deb-pkg-tools/commit/8b04dfcd4d3

`Release 1.22.5`_ (2014-06-22)
------------------------------

Preserving Python 2.x *and* Python 3.x compatibility is hard 😞.

.. _Release 1.22.5: https://github.com/xolox/python-deb-pkg-tools/compare/1.22.4...1.22.5

`Release 1.22.4`_ (2014-06-22)
------------------------------

Bug fix: Encode stdout/stderr as UTF-8 when not connected to a terminal.

.. _Release 1.22.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.22.3...1.22.4

`Release 1.22.3`_ (2014-06-19)
------------------------------

Bug fix for Python 3 syntax compatibility.

.. _Release 1.22.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.22.2...1.22.3

`Release 1.22.2`_ (2014-06-19)
------------------------------

Make the package cache resistant against deserialization errors.

Today I've been hitting zlib decoding errors and I'm 99% sure my disk isn't
failing (RAID 1 array). For now I'm inclined not to dive too deep into this,
because there's a very simple fix (see first line :-). For future reference,
here's the zlib error::

  File ".../deb_pkg_tools/cache.py", line 299, in control_fields
    return self.cache.decode(self['control_fields'])
  File ".../deb_pkg_tools/cache.py", line 249, in decode
    return pickle.loads(zlib.decompress(database_value))

  error: Error -5 while decompressing data

.. _Release 1.22.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.22.1...1.22.2

`Release 1.22.1`_ (2014-06-16)
------------------------------

- Change ``clean_package_tree()`` to clean up ``__pycache__`` directories.
- Improved test coverage of ``check_duplicate_files()``.

.. _Release 1.22.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.22...1.22.1

`Release 1.22`_ (2014-06-09)
----------------------------

Proof of concept: duplicate files check (static analysis).

.. _Release 1.22: https://github.com/xolox/python-deb-pkg-tools/compare/1.21...1.22

`Release 1.21`_ (2014-06-09)
----------------------------

Implement proper package metadata cache using SQLite 3.x (high performance).

I've been working on CPU and disk I/O intensive package analysis across
hundreds of package archives which is very slow even on my MacBook Air with
four cores and an SSD. I decided to rip the ad-hoc cache in ``scan_packages()``
out and refactor it into a more general purpose persistent, multiprocess cache
implemented on top of SQLite 3.x.

.. _Release 1.21: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.11...1.21

`Release 1.20.11`_ (2014-06-08)
-------------------------------

Improve performance: Cache results of ``RelationshipSet.matches()``.

.. _Release 1.20.11: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.10...1.20.11

`Release 1.20.10`_ (2014-06-08)
-------------------------------

Make ``deb_pkg_tools.utils.atomic_lock()`` blocking by default.

.. _Release 1.20.10: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.9...1.20.10

`Release 1.20.9`_ (2014-06-07)
------------------------------

Make it possible to ask a ``RelationshipSet`` for all its names.

.. _Release 1.20.9: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.8...1.20.9

`Release 1.20.8`_ (2014-06-07)
------------------------------

Bug fix for Python 3.x compatibility.

.. _Release 1.20.8: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.7...1.20.8

`Release 1.20.7`_ (2014-06-07)
------------------------------

Sanitize permission bits of root directory when building packages.

.. _Release 1.20.7: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.6...1.20.7

`Release 1.20.6`_ (2014-06-07)
------------------------------

Switch to executor 1.3 which supports ``execute(command, fakeroot=True)``.

.. _Release 1.20.6: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.5...1.20.6

`Release 1.20.5`_ (2014-06-05)
------------------------------

Added ``deb_pkg_tools.control.load_control_file()`` function.

.. _Release 1.20.5: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.4...1.20.5

`Release 1.20.4`_ (2014-06-01)
------------------------------

Minor optimization that seems to make a major difference (without this
optimization I would sometimes hit "recursion depth exceeded" errors).

.. _Release 1.20.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.3...1.20.4

`Release 1.20.3`_ (2014-06-01)
------------------------------

Bug fix for Python 3.x compatibility (missed ``compat.basestring`` import).

.. _Release 1.20.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.2...1.20.3

`Release 1.20.2`_ (2014-06-01)
------------------------------

Bug fix for Python 3.x incompatible syntax in newly added code.

.. _Release 1.20.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.20.1...1.20.2

`Release 1.20.1`_ (2014-06-01)
------------------------------

Automatically create parent directories in ``atomic_lock`` class.

.. _Release 1.20.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.20...1.20.1

`Release 1.20`_ (2014-06-01)
----------------------------

Re-implemented ``dpkg-scanpackages -m`` in Python to make it really fast.

.. _Release 1.20: https://github.com/xolox/python-deb-pkg-tools/compare/1.19...1.20

`Release 1.19`_ (2014-06-01)
----------------------------

Added function ``deb_pkg_tools.package.find_package_archives()``.

.. _Release 1.19: https://github.com/xolox/python-deb-pkg-tools/compare/1.18.5...1.19

`Release 1.18.5`_ (2014-05-28)
------------------------------

Bug fix for ``find_latest_version()`` introduced in commit 5bf01b0_ (`build
failure <https://travis-ci.org/xolox/python-deb-pkg-tools/jobs/26247681>`_ on
Travis CI).

.. _Release 1.18.5: https://github.com/xolox/python-deb-pkg-tools/compare/1.18.4...1.18.5
.. _5bf01b0: https://github.com/xolox/python-deb-pkg-tools/commit/5bf01b0


`Release 1.18.4`_ (2014-05-28)
------------------------------

Disable pretty printing of ``RelationshipSet`` objects by default.

.. _Release 1.18.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.18.3...1.18.4

`Release 1.18.3`_ (2014-05-26)
------------------------------

- Fixed sort order of ``deb_pkg_tools.package.PackageFile`` (changed field order)
- Sanity check given arguments in ``deb_pkg_tools.package.find_latest_version()``.
- Documented the exception that can be raised by ``deb_pkg_tools.package.parse_filename()``.

.. _Release 1.18.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.18.2...1.18.3

`Release 1.18.2`_ (2014-05-26)
------------------------------

Change ``deb_pkg_tools.deps.parse_depends()`` to accept a list of dependencies.

.. _Release 1.18.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.18.1...1.18.2

`Release 1.18.1`_ (2014-05-25)
------------------------------

- Bug fix for last commit (avoid ``AttributeError`` on ``apt_pkg.version_compare``).
- Changed documentation of ``deb_pkg_tools.compat`` module.
- Made doctest examples Python 3.x compatible (``print()`` as function).
- Integrate customized doctest checking in makefile.

.. _Release 1.18.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.18...1.18.1

`Release 1.18`_ (2014-05-25)
----------------------------

Extract version comparison to separate module (with tests).

I wanted to re-use version sorting in several places so it seemed logical to
group the related code together in a new ``deb_pkg_tools.version`` module.
While I was at it I decided to write tests that make sure the results of
``compare_versions_with_python_apt()`` and ``compare_versions_with_dpkg()`` are
consistent with each other and the expected behavior.

.. _Release 1.18: https://github.com/xolox/python-deb-pkg-tools/compare/1.17.7...1.18

`Release 1.17.7`_ (2014-05-18)
------------------------------

Made ``collect_related_packages()`` faster (by splitting ``inspect_package()``).

.. _Release 1.17.7: https://github.com/xolox/python-deb-pkg-tools/compare/1.17.6...1.17.7

`Release 1.17.6`_ (2014-05-18)
------------------------------

Re-implemented ``dpkg_compare_versions()`` on top of ``apt.VersionCompare()``.

.. _Release 1.17.6: https://github.com/xolox/python-deb-pkg-tools/compare/1.17.5...1.17.6

`Release 1.17.5`_ (2014-05-18)
------------------------------

Moved Python 2.x / 3.x compatibility functions to a separate module.

.. _Release 1.17.5: https://github.com/xolox/python-deb-pkg-tools/compare/1.17.4...1.17.5

`Release 1.17.4`_ (2014-05-18)
------------------------------

- Made pretty print tests compatible with Python 3.x.
- Removed ``binutils`` and ``tar`` dependencies (these are no longer needed
  since the ``inspect_package()`` function now uses the ``dpkg-deb`` command).

.. _Release 1.17.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.17.3...1.17.4

`Release 1.17.3`_ (2014-05-18)
------------------------------

- Cleanup pretty printer, remove monkey patching hack, add tests.
- Dedent string passed to ``deb822_from_string()`` (nice to use in tests).

.. _Release 1.17.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.17.2...1.17.3

`Release 1.17.2`_ (2014-05-18)
------------------------------

- Bug fix for output of ``deb-pkg-tools --inspect ...`` (broken in Python 3.x
  compatibility spree).
- Monkey patch pprint so it knows how to 'pretty print' ``RelationshipSet``
  (very useful to verify docstrings containing doctest blocks).
- Improved test coverage of ``deb_pkg_tools.package.PackageFile.__lt__()``.

.. _Release 1.17.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.17.1...1.17.2

`Release 1.17.1`_ (2014-05-18)
------------------------------

- Bug fix for ``deb_pkg_tools.deps.parse_relationship()``.
- Bug fix for ``inspect_package()`` (hard links weren't recognized).
- Added ``deb_pkg_tools.control.deb822_from_string()`` shortcut.
- Various bug fixes for Python 2.6 and 3.x compatibility:

  - Bumped ``python-debian`` requirement to ``0.1.21-nmu2`` for Python 3.x compatibility
  - Changed ``logger.warn()`` to ``logger.warning()`` (the former is deprecated).
  - Fixed missing ``str_compatible`` decorator (Python 3.x compatibility).

.. _Release 1.17.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.17...1.17.1

`Release 1.17`_ (2014-05-18)
----------------------------

Added ``collect_related_packages()`` function and ``deb-pkg-tools --collect``
command line interface.

.. _Release 1.17: https://github.com/xolox/python-deb-pkg-tools/compare/1.16...1.17

`Release 1.16`_ (2014-05-18)
----------------------------

- Added relationship parsing/evaluation module (``deb_pkg_tools.deps.*``).
- Bug fix for ``deb_pkg_tools.generate_stdeb_cfg()``.
- Test suite changes:

  - Skip repository activation in ``test_command_line_interface()`` when not ``root``.
  - Added an improvised slow test marker.

.. _Release 1.16: https://github.com/xolox/python-deb-pkg-tools/compare/1.15.2...1.16

`Release 1.15.2`_ (2014-05-16)
------------------------------

- Added ``deb_pkg_tools.package.parse_filename()`` function.
- Properly document ``deb_pkg_tools.package.ArchiveEntry`` named tuple.
- Improved test coverage by testing command line interface.
- Changed virtual environment handling in ``Makefile``.

.. _Release 1.15.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.15.1...1.15.2

`Release 1.15.1`_ (2014-05-10)
------------------------------

- `Bug fix for Python 3 compatibility <https://travis-ci.org/xolox/python-deb-pkg-tools/jobs/24867811>`_.

- Moved ``deb_pkg_tools.cli.with_repository()`` to ``deb_pkg_tools.repo.with_repository()``.

- Submit test coverage from travis-ci.org to coveralls.io, add dynamic coverage
  statistics to ``README.rst``.

- Run more tests on travis-ci.org by running test suite as root (this gives the
  test suite permission to test things like apt-get local repository
  activation).

- Improved test coverage of ``deb_pkg_tools.repository.update_repository()``
  and ``deb_pkg_tools.gpg.GPGKey()``.

.. _Release 1.15.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.15...1.15.1

`Release 1.15`_ (2014-05-10)
----------------------------

- Merge pull request `#1`_: Python 3 compatibility.
- Document supported Python versions (2.6, 2.7 & 3.4).
- Start using travis-ci.org to avoid dropping Python 3 compatibility in the future.
- Update documented dependencies in ``README.rst``.

.. _Release 1.15: https://github.com/xolox/python-deb-pkg-tools/compare/1.14.7...1.15
.. _#1: ttps://github.com/xolox/python-deb-pkg-tools/pull/1

`Release 1.14.7`_ (2014-05-04)
------------------------------

Refactored ``deb_pkg_tools.utils.execute()`` into a separate package.

.. _Release 1.14.7: https://github.com/xolox/python-deb-pkg-tools/compare/1.14.6...1.14.7

`Release 1.14.6`_ (2014-05-03)
------------------------------

Bug fix for globbing support.

.. _Release 1.14.6: https://github.com/xolox/python-deb-pkg-tools/compare/1.14.5...1.14.6

`Release 1.14.5`_ (2014-05-03)
------------------------------

Added support for ``deb-pkg-tools --patch=CTRL_FILE --set="Name: Value"``.

.. _Release 1.14.5: https://github.com/xolox/python-deb-pkg-tools/compare/1.14.4...1.14.5

`Release 1.14.4`_ (2014-05-03)
------------------------------

Make ``update_repository()`` as "atomic" as possible.

.. _Release 1.14.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.14.3...1.14.4

`Release 1.14.3`_ (2014-05-03)
------------------------------

Support for globbing in configuration file (``repos.ini``).

.. _Release 1.14.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.14.2...1.14.3

`Release 1.14.2`_ (2014-04-29)
------------------------------

Bug fix: Typo in readme (found just after publishing of course 😉).

.. _Release 1.14.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.14.1...1.14.2

`Release 1.14.1`_ (2014-04-29)
------------------------------

Added support for the system wide configuration file ``/etc/deb-pkg-tools/repos.ini``.

.. _Release 1.14.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.14...1.14.1

`Release 1.14`_ (2014-04-29)
----------------------------

- Make repository generation user configurable (``~/.deb-pkg-tools/repos.ini``).
- Test GPG key generation (awkward but useful, make it opt-in or opt-out?).
- Make Python >= 2.6 dependency explicit in stdeb.cfg (part 2 :-).
- Documentation bug fix: Update usage message and ``README.rst``.

.. _Release 1.14: https://github.com/xolox/python-deb-pkg-tools/compare/1.13.2...1.14

`Release 1.13.2`_ (2014-04-28)
------------------------------

Bug fix: Respect the ``build_package(copy_files=False)`` option.

.. _Release 1.13.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.13.1...1.13.2

`Release 1.13.1`_ (2014-04-28)
------------------------------

- Try to detect removal of ``*.deb`` files in ``update_repository()``.
- Bring test coverage back up to >= 90%.

.. _Release 1.13.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.13...1.13.1

`Release 1.13`_ (2013-11-16)
----------------------------

Make ``inspect_package()`` report package contents. This was added to make it
easier to write automated tests for deb-pkg-tools but may be useful in other
circumstances and so became part of the public API 😇.

.. _Release 1.13: https://github.com/xolox/python-deb-pkg-tools/compare/1.12.1...1.13

`Release 1.12.1`_ (2013-11-03)
------------------------------

Make Python >= 2.6 dependency explicit in ``stdeb.cfg``.

.. _Release 1.12.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.12...1.12.1

`Release 1.12`_ (2013-11-03)
----------------------------

Make ``copy_package_files()`` more generally useful.

.. _Release 1.12: https://github.com/xolox/python-deb-pkg-tools/compare/1.11...1.12

`Release 1.11`_ (2013-11-02)
----------------------------

- Improve ``deb_pkg_tools.gpg.GPGKey`` and related documentation.

.. _Release 1.11: https://github.com/xolox/python-deb-pkg-tools/compare/1.10.2...1.11

`Release 1.10.2`_ (2013-11-02)
------------------------------

Bug fix: Make ``update_repository()`` always remove old ``Release.gpg`` files.

.. _Release 1.10.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.10.1...1.10.2

`Release 1.10.1`_ (2013-11-02)
------------------------------

Bug fix: Make ``update_repository()`` fully aware of ``apt_supports_trusted_option()``.

.. _Release 1.10.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.10...1.10.1

`Release 1.10`_ (2013-11-02)
----------------------------

Use the ``[trusted=yes]`` option in ``sources.list`` when possible:

With this we no longer need a generated GPG key at all; we just skip all steps
that have anything to do with GPG :-). Unfortunately we still need to be
backwards compatible so the code to generate and manage GPG keys remains for
now...

.. _Release 1.10: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.9...1.10

`Release 1.9.9`_ (2013-10-22)
-----------------------------

Remove automatic dependency installation (too much magic, silly idea).

.. _Release 1.9.9: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.8...1.9.9

`Release 1.9.8`_ (2013-10-22)
-----------------------------

Bug fixes for last commit (sorry about that!).

.. _Release 1.9.8: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.7...1.9.8

`Release 1.9.7`_ (2013-10-22)
-----------------------------

New ``deb-pkg-tools --with-repo=DIR COMMAND...`` functionality (only exposed in
the command line interface for now).

.. _Release 1.9.7: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.6...1.9.7

`Release 1.9.6`_ (2013-10-21)
-----------------------------

Workaround for old and buggy versions of GnuPG 😞.

.. _Release 1.9.6: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.5...1.9.6

`Release 1.9.5`_ (2013-10-20)
-----------------------------

Bug fix for ``update_repository()``.

.. _Release 1.9.5: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.4...1.9.5

`Release 1.9.4`_ (2013-10-20)
-----------------------------

Change ``update_repository()`` to only rebuild repositories when contents have changed.

.. _Release 1.9.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.3...1.9.4

`Release 1.9.3`_ (2013-10-20)
-----------------------------

Make ``update_conffiles()`` work properly in Python < 2.7.

.. _Release 1.9.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.2...1.9.3

`Release 1.9.2`_ (2013-10-20)
-----------------------------

Enable overriding of GPG key used by the ``deb_pkg_tools.repo.*`` functions.

.. _Release 1.9.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.9.1...1.9.2

`Release 1.9.1`_ (2013-10-20)
-----------------------------

Made it possible not to copy the files in the build directory (``build_package()``).

.. _Release 1.9.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.9...1.9.1

`Release 1.9`_ (2013-10-20)
---------------------------

Extracted GPG key generation into standalone function.

.. _Release 1.9: https://github.com/xolox/python-deb-pkg-tools/compare/1.8...1.9

`Release 1.8`_ (2013-10-20)
---------------------------

Automatic installation of required system packages.

.. _Release 1.8: https://github.com/xolox/python-deb-pkg-tools/compare/1.7.2...1.8

`Release 1.7.2`_ (2013-10-19)
-----------------------------

Make ``copy_package_files()`` compatible with ``schroot`` environments.

.. _Release 1.7.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.7.1...1.7.2

`Release 1.7.1`_ (2013-10-18)
-----------------------------

Enable callers of ``update_repository()`` to set fields of ``Release`` files.

.. _Release 1.7.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.7...1.7.1

`Release 1.7`_ (2013-10-16)
---------------------------

Change ``build_package()`` to automatically update ``DEBIAN/conffiles``.

.. _Release 1.7: https://github.com/xolox/python-deb-pkg-tools/compare/1.6.2...1.7

`Release 1.6.2`_ (2013-10-13)
-----------------------------

Bug fix: Make ``deb-pkg-tools -u`` and ``deb-pkg-tools -a`` compatible with ``schroot`` environments.

.. _Release 1.6.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.6.1...1.6.2

`Release 1.6.1`_ (2013-10-12)
-----------------------------

Added ``stdeb.cfg`` to ``MANIFEST.in``.

.. _Release 1.6.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.6...1.6.1

`Release 1.6`_ (2013-10-12)
---------------------------

- Improved documentation of ``deb_pkg_tools.utils.execute()``.
- Improved ``deb_pkg_tools.utils.execute()``, implemented optional ``sudo`` support.

.. _Release 1.6: https://github.com/xolox/python-deb-pkg-tools/compare/1.5...1.6

`Release 1.5`_ (2013-10-12)
---------------------------

Automatically generate a GPG automatic signing key the first time it's needed.

.. _Release 1.5: https://github.com/xolox/python-deb-pkg-tools/compare/1.4.3...1.5

`Release 1.4.3`_ (2013-10-12)
-----------------------------

- Made log messages more user friendly.
- Made Debian package dependencies available from Python.

.. _Release 1.4.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.4.2...1.4.3

`Release 1.4.2`_ (2013-10-12)
-----------------------------

Make it possible to delete fields using ``patch_control_file()``.

.. _Release 1.4.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.4.1...1.4.2

`Release 1.4.1`_ (2013-08-13)
-----------------------------

Improved ``update_installed_size()`` (by using ``patch_control_file()``).

.. _Release 1.4.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.4...1.4.1

`Release 1.4`_ (2013-08-13)
---------------------------

Normalize field names in control files (makes merging easier).

.. _Release 1.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.3.2...1.4

`Release 1.3.2`_ (2013-08-13)
-----------------------------

Make ``build_package()`` sanitize file modes:

I was debating with myself for quite a while how far to go in these kinds of
"sensible defaults"; there will always be someone who doesn't want the
behavior. I decided that those people shouldn't be using deb-pkg-tools then :-)
(I wonder how long it takes though, before I find myself in that group of
people ;-).

.. _Release 1.3.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.3.1...1.3.2

`Release 1.3.1`_ (2013-08-11)
-----------------------------

Improved ``clean_package_tree()`` (better documentation, more files to ignore).

.. _Release 1.3.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.3...1.3.1

`Release 1.3`_ (2013-08-11)
---------------------------

Added ``clean_package_tree()`` function.

.. _Release 1.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.2...1.3

`Release 1.2`_ (2013-08-10)
---------------------------

Added ``patch_control_file()`` function.

.. _Release 1.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.1.4...1.2

`Release 1.1.4`_ (2013-08-10)
-----------------------------

Removed as much manual shell quoting as possible.

.. _Release 1.1.4: https://github.com/xolox/python-deb-pkg-tools/compare/1.1.3...1.1.4

`Release 1.1.3`_ (2013-08-10)
-----------------------------

- Silenced ``deb_pkg_tools.utils.execute()``
- Simplified ``deb_pkg_tools.package.inspect_package()``.

.. _Release 1.1.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.1.2...1.1.3

`Release 1.1.2`_ (2013-08-07)
-----------------------------

Started using ``coloredlogs.increase_verbosity()``.

.. _Release 1.1.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.1.1...1.1.2

`Release 1.1.1`_ (2013-08-07)
-----------------------------

Loosen up the requirements (stop using absolute version pinning).

.. _Release 1.1.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.1...1.1.1

`Release 1.1`_ (2013-08-05)
---------------------------

Automatically run Lintian after building packages.

.. _Release 1.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.0.3...1.1

`Release 1.0.3`_ (2013-08-04)
-----------------------------

Improved wording of readme, fixed typo in docs.

.. _Release 1.0.3: https://github.com/xolox/python-deb-pkg-tools/compare/1.0.2...1.0.3

`Release 1.0.2`_ (2013-08-04)
-----------------------------

Got rid of the use of shell pipes in order to detect "command not found" errors.

.. _Release 1.0.2: https://github.com/xolox/python-deb-pkg-tools/compare/1.0.1...1.0.2

`Release 1.0.1`_ (2013-08-04)
-----------------------------

Brought test suite coverage up to 96% 🎉.

.. _Release 1.0.1: https://github.com/xolox/python-deb-pkg-tools/compare/1.0...1.0.1

`Release 1.0`_ (2013-07-26)
---------------------------

Initial commit with a focus on:

- Building of Debian binary packages.
- Inspecting the metadata of Debian binary packages.
- Creation of trivial repositories based on collected package metadata.

.. _Release 1.0: https://github.com/xolox/python-deb-pkg-tools/tree/1.0
