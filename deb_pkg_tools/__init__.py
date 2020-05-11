# Debian packaging tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 11, 2020
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
The top-level :mod:`deb_pkg_tools` module.

The :mod:`deb_pkg_tools` module defines the `deb-pkg-tools` version number and
the Debian packages that are required to use all of the features provided by
the `deb-pkg-tools` package.
"""

# Semi-standard module versioning.
__version__ = '8.3'

debian_package_dependencies = (
    'apt',        # apt-get
    'apt-utils',  # apt-ftparchive
    'dpkg-dev',   # dpkg-architecture
    'fakeroot',   # fakeroot
    'gnupg',      # gpg
    'lintian',    # lintian
)
"""A tuple of strings with required Debian packages."""


def generate_stdeb_cfg():
    """
    Generate the contents of the ``stdeb.cfg`` file used by stdeb_ and py2deb_.

    The Debian package dependencies and minimal Python version are included in
    the output.

    .. _stdeb: https://pypi.python.org/pypi/stdeb
    .. _py2deb: https://pypi.python.org/pypi/py2deb
    """
    print('[deb-pkg-tools]')
    print('Recommends: %s' % ', '.join(debian_package_dependencies))
    print('Suggests: memcached')
