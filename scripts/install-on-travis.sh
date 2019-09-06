#!/bin/bash -e

# Install the dependencies of deb-pkg-tools before running the test suite.
# For more information about the nasty /dev/random hack, please see:
# https://github.com/travis-ci/travis-ci/issues/1913#issuecomment-33891474
sudo apt-get update -qq
sudo apt-get install --yes dpkg-dev fakeroot lintian memcached python-apt python3-apt rng-tools
sudo rm -f /dev/random
sudo mknod -m 0666 /dev/random c 1 9
echo HRNGDEVICE=/dev/urandom | sudo tee /etc/default/rng-tools
sudo /etc/init.d/rng-tools restart

# We ignore the Python virtual environment provided by Travis CI and instead
# create our own virtual environment, with the intention of making it possible
# to import the apt_pkg module (which is installed system wide because it's
# available via apt but not on PyPI).
INTERPRETER=$(python -c 'import sys; print("python%i.%i" % sys.version_info[:2])')
PREFERRED_PATH=/usr/bin/$INTERPRETER
if [ -x $PREFERRED_PATH ]; then
  # If possible we create the virtual environment based on a Python
  # installation provided by Ubuntu instead of Travis CI. At the time of
  # writing this works for Python 2.7, 3.4, 3.5 and 3.6 but not 3.7.
  INTERPRETER=$PREFERRED_PATH
fi
echo "Recreating virtual environment ($VIRTUAL_ENV) using $INTERPRETER .."
rm -r $VIRTUAL_ENV
# Given that we're recreating the virtual environment we can
# enable access to the system-wide site-packages directory.
virtualenv --python=$INTERPRETER --system-site-packages $VIRTUAL_ENV

# Install the required Python packages.
pip install --constraint=constraints.txt --requirement=requirements-travis.txt

# Install the project itself, making sure that potential character encoding
# and/or decoding errors in the setup script are caught as soon as possible.
LC_ALL=C pip install .
