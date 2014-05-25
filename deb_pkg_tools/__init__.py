# Debian packaging tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 25, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

# Standard library modules.
import logging

# Initialize a logger.
logger = logging.getLogger(__name__)

# Semi-standard module versioning.
__version__ = '1.18'

# The following non-essential Debian packages need to be
# installed in order for deb-pkg-tools to work properly.
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
    print('[deb-pkg-tools]')
    print('Depends: %s' % ', '.join(debian_package_dependencies))
    print('XS-Python-Version: >= 2.6')

# vim: ts=4 sw=4 et
