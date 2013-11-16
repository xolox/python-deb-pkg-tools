# Debian packaging tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 16, 2013
# URL: https://github.com/xolox/python-deb-pkg-tools

# Standard library modules.
import logging

# Initialize a logger.
logger = logging.getLogger(__name__)

# Semi-standard module versioning.
__version__ = '1.13'

# The following non-essential Debian packages need to be
# installed in order for deb-pkg-tools to work properly.
debian_package_dependencies = (
    'apt',       # apt-get
    'apt-utils', # apt-ftparchive
    'binutils',  # ar
    'dpkg-dev',  # dpkg-scanpackages
    'fakeroot',  # fakeroot
    'gnupg',     # gpg
    'lintian',   # lintian
)

def generate_stdeb_cfg():
    print '[deb-pkg-tools]'
    print 'Depends:', ', '.join(debian_package_dependencies)

# vim: ts=4 sw=4 et
