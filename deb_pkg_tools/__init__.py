# Debian packaging tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 17, 2018
# URL: https://github.com/xolox/python-deb-pkg-tools

"""
The top-level :mod:`deb_pkg_tools` module.

The :mod:`deb_pkg_tools` module defines the `deb-pkg-tools` version number and
the Debian packages that are required to use all of the features provided by
the `deb-pkg-tools` package.
"""

# Semi-standard module versioning.
__version__ = '5.2'

debian_package_dependencies = (
    'apt',        # apt-get
    'apt-utils',  # apt-ftparchive
    'dpkg-dev',   # dpkg-architecture
    'fakeroot',   # fakeroot
    'gnupg',      # gpg
    'lintian',    # lintian
    'python-apt',
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
    print('Depends: python-apt')
    print('Recommends: %s' % ', '.join(pkg for pkg in debian_package_dependencies if pkg != 'python-apt'))
    print('Suggests: memcached')
