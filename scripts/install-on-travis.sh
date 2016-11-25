#!/bin/bash -e

# Install the dependencies of deb-pkg-tools before running the test suite.
# For more information about the nasty /dev/random hack, please see:
# https://github.com/travis-ci/travis-ci/issues/1913#issuecomment-33891474
sudo apt-get update -qq
sudo apt-get install --yes dpkg-dev fakeroot lintian memcached python-apt rng-tools
sudo rm -f /dev/random
sudo mknod -m 0666 /dev/random c 1 9
echo HRNGDEVICE=/dev/urandom | sudo tee /etc/default/rng-tools
sudo /etc/init.d/rng-tools restart

# Install the required Python packages.
pip install pip-accel
pip-accel install coveralls
pip-accel install --requirement=requirements.txt
pip-accel install --requirement=requirements-checks.txt
pip-accel install --requirement=requirements-tests.txt

# Install the project itself, making sure that potential character encoding
# and/or decoding errors in the setup script are caught as soon as possible.
LC_ALL=C pip-accel install .
