# Debian packaging tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: June 1, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

# Semi-standard module versioning.
__version__ = '1.20.1'

debian_package_dependencies = (
    'apt',        # apt-get
    'apt-utils',  # apt-ftparchive
    'dpkg-dev',   # dpkg-scanpackages
    'fakeroot',   # fakeroot
    'gnupg',      # gpg
    'lintian',    # lintian
    'python-apt',
)

def generate_stdeb_cfg():
    """
    Generate the contents of the ``stdeb.cfg`` file used by stdeb_. The Debian
    package dependencies and minimal Python version are included in the output.

    .. _stdeb: https://pypi.python.org/pypi/stdeb
    """
    print('[deb-pkg-tools]')
    print('Depends: %s' % ', '.join(debian_package_dependencies))
    print('XS-Python-Version: >= 2.6')

# vim: ts=4 sw=4 et
