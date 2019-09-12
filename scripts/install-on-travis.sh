#!/bin/bash -e

main () {

  # Install the dependencies of deb-pkg-tools before running the test suite.
  # For more information about the nasty /dev/random hack, please see:
  # https://github.com/travis-ci/travis-ci/issues/1913#issuecomment-33891474
  msg "Updating package lists .."
  sudo apt-get update -qq
  msg "Installing system dependencies .."
  sudo apt-get install --yes dpkg-dev fakeroot lintian memcached python-apt python3-apt rng-tools
  msg "Reconfiguring rng-tools .."
  sudo rm -f /dev/random
  sudo mknod -m 0666 /dev/random c 1 9
  echo HRNGDEVICE=/dev/urandom | sudo tee /etc/default/rng-tools
  sudo /etc/init.d/rng-tools restart

  # When possible we ignore the Python virtual environment provided by Travis CI
  # and instead create our own virtual environment based on a system wide Python
  # installation provided by Ubuntu, with the intention of making it possible to
  # import the apt_pkg module (which is installed system wide because it's
  # available via apt but not on PyPI).
  msg "Checking whether virtual environment can be recreated ($VIRTUAL_ENV) .."
  CURRENT_INTERPRETER=$(python -c 'import sys; print("python%i.%i" % sys.version_info[:2])')
  PREFERRED_EXECUTABLE=/usr/bin/$CURRENT_INTERPRETER
  if [ -x $PREFERRED_EXECUTABLE ]; then
    msg "Recreating virtual environment based on $PREFERRED_EXECUTABLE .."
    rm -r $VIRTUAL_ENV
    virtualenv --python=$PREFERRED_EXECUTABLE --system-site-packages $VIRTUAL_ENV
  else
    msg "Not recreating virtual environment ($PREFERRED_EXECUTABLE not available) .."
  fi

  # Install the required Python packages.
  msg "Installing Python dependencies .."
  pip install --constraint=constraints.txt --requirement=requirements-travis.txt

  # Install the project itself, making sure that potential character encoding
  # and/or decoding errors in the setup script are caught as soon as possible.
  msg "Installing Python package .."
  LC_ALL=C pip install .

}

msg () {
  echo "[install-on-travis] $*" >&2
}

main "$@"
