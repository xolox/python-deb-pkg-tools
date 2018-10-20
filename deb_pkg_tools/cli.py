# Debian packaging tools: Command line interface
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: October 20, 2018
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
Usage: deb-pkg-tools [OPTIONS] ...

Wrapper for the deb-pkg-tools Python project that implements various tools to
inspect, build and manipulate Debian binary package archives and related
entities like trivial repositories.

Supported options:

  -i, --inspect=FILE

    Inspect the metadata in the Debian binary package archive given by FILE
    (similar to `dpkg --info').

  -c, --collect=DIR

    Copy the package archive(s) given as positional arguments (and all package
    archives required by the given package archives) into the directory given
    by DIR.

  -C, --check=FILE

    Perform static analysis on a package archive and its dependencies in order
    to recognize common errors as soon as possible.

  -p, --patch=FILE

    Patch fields into the existing control file given by FILE. To be used
    together with the -s, --set option.

  -s, --set=LINE

    A line to patch into the control file (syntax: "Name: Value"). To be used
    together with the -p, --patch option.

  -b, --build=DIR

    Build a Debian binary package with `dpkg-deb --build' (and lots of
    intermediate Python magic, refer to the API documentation of the project
    for full details) based on the binary package template in the directory
    given by DIR. The resulting archive is located in the system wide
    temporary directory (usually /tmp).

  -u, --update-repo=DIR

    Create or update the trivial Debian binary package repository in the
    directory given by DIR.

  -a, --activate-repo=DIR

    Enable `apt-get' to install packages from the trivial repository (requires
    root/sudo privilege) in the directory given by DIR. Alternatively you can
    use the -w, --with-repo option.

  -d, --deactivate-repo=DIR

    Cleans up after --activate-repo (requires root/sudo privilege).
    Alternatively you can use the -w, --with-repo option.

  -w, --with-repo=DIR

    Create or update a trivial package repository, activate the repository, run
    the positional arguments as an external command (usually `apt-get install')
    and finally deactivate the repository.

  --gc, --garbage-collect

    Force removal of stale entries from the persistent (on disk) package
    metadata cache. Garbage collection is performed automatically by the
    deb-pkg-tools command line interface when the last garbage collection
    cycle was more than 24 hours ago, so you only need to do it manually
    when you want to control when it happens (for example by a daily
    cron job scheduled during idle hours :-).

  -y, --yes

    Assume the answer to interactive questions is yes.

  -v, --verbose

    Make more noise! (useful during debugging)

  -h, --help

    Show this message and exit.
"""

# Standard library modules.
import codecs
import functools
import getopt
import logging
import multiprocessing
import os.path
import shutil
import sys
import tempfile

# External dependencies.
import coloredlogs
from humanfriendly import AutomaticSpinner, format_path, format_size, parse_path
from humanfriendly.text import compact, format, pluralize
from humanfriendly.prompts import prompt_for_confirmation
from humanfriendly.terminal import (
    HIGHLIGHT_COLOR,
    ansi_wrap,
    terminal_supports_colors,
    usage,
    warning,
)

# Modules included in our package.
from deb_pkg_tools.cache import get_default_cache
from deb_pkg_tools.checks import check_package
from deb_pkg_tools.control import patch_control_file
from deb_pkg_tools.package import (build_package, collect_related_packages,
                                   inspect_package, parse_filename)
from deb_pkg_tools.repo import (update_repository,
                                activate_repository,
                                deactivate_repository,
                                with_repository)

# Initialize a logger.
logger = logging.getLogger(__name__)

OUTPUT_ENCODING = 'UTF-8'


def main():
    """Command line interface for the ``deb-pkg-tools`` program."""
    # Configure logging output.
    coloredlogs.install()
    # Command line option defaults.
    prompt = True
    actions = []
    control_file = None
    control_fields = {}
    directory = None
    # Initialize the package cache.
    cache = get_default_cache()
    # Parse the command line options.
    try:
        options, arguments = getopt.getopt(sys.argv[1:], 'i:c:C:p:s:b:u:a:d:w:yvh', [
            'inspect=', 'collect=', 'check=', 'patch=', 'set=', 'build=',
            'update-repo=', 'activate-repo=', 'deactivate-repo=', 'with-repo=',
            'gc', 'garbage-collect', 'yes', 'verbose', 'help'
        ])
        for option, value in options:
            if option in ('-i', '--inspect'):
                actions.append(functools.partial(show_package_metadata, archive=value))
            elif option in ('-c', '--collect'):
                directory = check_directory(value)
            elif option in ('-C', '--check'):
                actions.append(functools.partial(check_package, archive=value, cache=cache))
            elif option in ('-p', '--patch'):
                control_file = os.path.abspath(value)
                assert os.path.isfile(control_file), "Control file does not exist!"
            elif option in ('-s', '--set'):
                name, _, value = value.partition(':')
                control_fields[name] = value.strip()
            elif option in ('-b', '--build'):
                actions.append(functools.partial(
                    build_package,
                    check_directory(value),
                    repository=tempfile.gettempdir(),
                ))
            elif option in ('-u', '--update-repo'):
                actions.append(functools.partial(update_repository,
                                                 directory=check_directory(value),
                                                 cache=cache))
            elif option in ('-a', '--activate-repo'):
                actions.append(functools.partial(activate_repository, check_directory(value)))
            elif option in ('-d', '--deactivate-repo'):
                actions.append(functools.partial(deactivate_repository, check_directory(value)))
            elif option in ('-w', '--with-repo'):
                actions.append(functools.partial(with_repository_wrapper,
                                                 directory=check_directory(value),
                                                 command=arguments,
                                                 cache=cache))
            elif option in ('--gc', '--garbage-collect'):
                actions.append(functools.partial(cache.collect_garbage, force=True))
            elif option in ('-y', '--yes'):
                prompt = False
            elif option in ('-v', '--verbose'):
                coloredlogs.increase_verbosity()
            elif option in ('-h', '--help'):
                usage(__doc__)
                return
        # We delay the patch_control_file() and collect_packages() partials
        # until all command line options have been parsed, to ensure that the
        # order of the command line options doesn't matter.
        if control_file:
            if not control_fields:
                raise Exception("Please specify one or more control file fields to patch!")
            actions.append(functools.partial(patch_control_file, control_file, control_fields))
        if directory:
            actions.append(functools.partial(collect_packages,
                                             archives=arguments,
                                             directory=directory,
                                             prompt=prompt,
                                             cache=cache))
    except Exception as e:
        warning("Error: %s", e)
        sys.exit(1)
    # Execute the selected action.
    try:
        if actions:
            for action in actions:
                action()
            cache.collect_garbage()
        else:
            usage(__doc__)
    except Exception:
        logger.exception("An error occurred! Aborting..")
        sys.exit(1)


def show_package_metadata(archive):
    """
    Show the metadata and contents of a Debian archive on the terminal.

    :param archive: The pathname of an existing ``*.deb`` archive (a string).
    """
    control_fields, contents = inspect_package(archive)
    say(highlight("Package metadata from %s:"), format_path(archive))
    for field_name in sorted(control_fields.keys()):
        value = control_fields[field_name]
        if field_name == 'Installed-Size':
            value = format_size(int(value) * 1024)
        say(" - %s %s", highlight(field_name + ":"), value)
    say(highlight("Package contents from %s:"), format_path(archive))
    for pathname, entry in sorted(contents.items()):
        size = format_size(entry.size, keep_width=True)
        if len(size) < 10:
            size = ' ' * (10 - len(size)) + size
        if entry.target:
            pathname += ' -> ' + entry.target
        say("{permissions} {owner} {group} {size} {modified} {pathname}",
            permissions=entry.permissions, owner=entry.owner,
            group=entry.group, size=size, modified=entry.modified,
            pathname=pathname)


def highlight(text):
    """
    Highlight a piece of text using ANSI escape sequences.

    :param text: The text to highlight (a string).
    :returns: The highlighted text (when standard output is connected to a
              terminal) or the original text (when standard output is not
              connected to a terminal).
    """
    if terminal_supports_colors(sys.stdout):
        text = ansi_wrap(text, color=HIGHLIGHT_COLOR)
    return text


def collect_packages(archives, directory, prompt=True, cache=None, concurrency=None):
    """
    Interactively copy packages and their dependencies.

    :param archives: An iterable of strings with the filenames of one or more
                     ``*.deb`` files.
    :param directory: The pathname of a directory where the package archives
                      and dependencies should be copied to (a string).
    :param prompt: :data:`True` (the default) to ask confirmation from the
                   operator (using a confirmation prompt rendered on the
                   terminal), :data:`False` to skip the prompt.
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    :param concurrency: Override the number of concurrent processes (defaults
                        to the number of `archives` given or to the value of
                        :func:`multiprocessing.cpu_count()`, whichever is
                        smaller).
    :raises: :exc:`~exceptions.ValueError` when no archives are given.

    When more than one archive is given a :mod:`multiprocessing` pool is used
    to collect related archives concurrently, in order to speed up the process
    of collecting large dependency sets.
    """
    archives = list(archives)
    related_archives = set(map(parse_filename, archives))
    if not archives:
        raise ValueError("At least one package archive is required!")
    elif len(archives) == 1:
        # Find the related packages of a single archive.
        related_archives.update(collect_related_packages(archives[0], cache=cache))
    else:
        # Find the related packages of multiple archives (concurrently).
        with AutomaticSpinner(label="Collecting related packages"):
            concurrency = min(len(archives), concurrency or multiprocessing.cpu_count())
            pool = multiprocessing.Pool(concurrency)
            try:
                arguments = [(archive, cache) for archive in archives]
                for result in pool.map(collect_packages_worker, arguments, chunksize=1):
                    related_archives.update(result)
            finally:
                pool.terminate()
    # Ignore package archives that are already in the target directory.
    relevant_archives = set()
    for archive in related_archives:
        basename = os.path.basename(archive.filename)
        if not os.path.isfile(os.path.join(directory, basename)):
            relevant_archives.add(archive)
    # Interactively move the package archives.
    if relevant_archives:
        relevant_archives = sorted(relevant_archives)
        pluralized = pluralize(len(relevant_archives), "package archive", "package archives")
        say("Found %s:", pluralized)
        for file_to_collect in relevant_archives:
            say(" - %s", format_path(file_to_collect.filename))
        prompt_text = "Copy %s to %s?" % (pluralized, format_path(directory))
        if prompt and not prompt_for_confirmation(prompt_text, default=True, padding=False):
            logger.warning("Not copying archive(s) to %s! (aborted by user)", format_path(directory))
        else:
            # Link or copy the file(s).
            for file_to_collect in relevant_archives:
                src = file_to_collect.filename
                dst = os.path.join(directory, os.path.basename(src))
                smart_copy(src, dst)
            logger.info("Done! Copied %s to %s.", pluralized, format_path(directory))
    else:
        logger.info("Nothing to do! (%s previously copied)",
                    pluralize(len(related_archives), "package archive"))


def collect_packages_worker(args):
    """Helper for :func:`collect_packages()` that enables concurrent collection."""
    try:
        return collect_related_packages(args[0], cache=args[1], interactive=False)
    except Exception:
        # Log a full traceback in the child process because the multiprocessing
        # module doesn't preserve the traceback when propagating the exception
        # to the parent process.
        logger.exception(compact("""
            Encountered unhandled exception during collection of related
            packages! (propagating exception to parent process)
        """))
        # Propagate the exception to the parent process.
        raise


def smart_copy(src, dst):
    """
    Create a hard link to or copy of a file.

    :param src: The pathname of the source file (a string).
    :param dst: The pathname of the target file (a string).

    This function first tries to create a hard link `dst` pointing to `src` and
    if that fails it will perform a regular file copy from `src` to `dst`. This
    is used by :func:`collect_packages()` in an attempt to conserve disk space
    when copying package archives between repositories on the same filesystem.
    """
    try:
        os.link(src, dst)
    except Exception:
        logger.debug("Copying %s -> %s using regular file copy ..", format_path(src), format_path(dst))
        shutil.copy(src, dst)
    else:
        logger.debug("Copied %s -> %s using hard link ..", format_path(src), format_path(dst))


def with_repository_wrapper(directory, command, cache):
    """
    Command line wrapper for :func:`deb_pkg_tools.repo.with_repository()`.

    :param directory: The pathname of a directory with ``*.deb`` archives (a
                      string).
    :param command: The command to execute (a list of strings).
    :param cache: The :class:`.PackageCache` to use (defaults to :data:`None`).
    """
    if not command:
        # Default to the user's shell (seems like a sensible default?)
        command = [os.environ.get('SHELL', '/bin/bash')]
    try:
        with_repository(directory, *command, cache=cache)
    except Exception:
        logger.exception("Caught an unhandled exception!")
        sys.exit(1)


def check_directory(argument):
    """
    Make sure a command line argument points to an existing directory.

    :param argument: The original command line argument.
    :returns: The absolute pathname of an existing directory.
    """
    directory = parse_path(argument)
    if not os.path.isdir(directory):
        msg = "Directory doesn't exist! (%s)"
        raise Exception(msg % directory)
    return directory


def say(text, *args, **kw):
    """Reliably print Unicode strings to the terminal (standard output stream)."""
    text = format(text, *args, **kw)
    try:
        print(text)
    except UnicodeEncodeError:
        print(codecs.encode(text, OUTPUT_ENCODING))
