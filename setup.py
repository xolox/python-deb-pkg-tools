#!/usr/bin/env python

# Setup script for the `deb-pkg-tools' package.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: July 16, 2015
# URL: https://github.com/xolox/python-deb-pkg-tools

import codecs
import re
from os.path import abspath, dirname, join
from setuptools import setup, find_packages

# Find the directory where the source distribution was unpacked.
source_directory = dirname(abspath(__file__))

# Find the current version.
module = join(source_directory, 'deb_pkg_tools', '__init__.py')
for line in open(module, 'r'):
    match = re.match(r'^__version__\s*=\s*["\']([^"\']+)["\']$', line)
    if match:
        version_string = match.group(1)
        break
else:
    raise Exception("Failed to extract version from %s!" % module)

# Fill in the long description (for the benefit of PyPI)
# with the contents of README.rst (rendered by GitHub).
readme_file = join(source_directory, 'README.rst')
with codecs.open(readme_file, 'r', 'utf-8') as handle:
    readme_text = handle.read()

# Fill in the "install_requires" field based on requirements.txt.
requirements = [l.strip() for l in open(join(source_directory, 'requirements.txt'), 'r') if not l.startswith('#')]

setup(name='deb-pkg-tools',
      version=version_string,
      description="Debian packaging tools",
      long_description=readme_text,
      url='https://deb-pkg-tools.readthedocs.org',
      author='Peter Odding',
      author_email='peter@peterodding.com',
      packages=find_packages(),
      entry_points=dict(console_scripts=['deb-pkg-tools = deb_pkg_tools.cli:main']),
      install_requires=requirements,
      test_suite='deb_pkg_tools.tests')
