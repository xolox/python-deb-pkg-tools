# Makefile for the `deb-pkg-tools' package.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: September 6, 2019
# URL: https://github.com/xolox/python-deb-pkg-tools

PACKAGE_NAME = deb-pkg-tools
WORKON_HOME ?= $(HOME)/.virtualenvs
VIRTUAL_ENV ?= $(WORKON_HOME)/$(PACKAGE_NAME)
PYTHON ?= python3
PATH := $(VIRTUAL_ENV)/bin:$(PATH)
MAKE := $(MAKE) --no-print-directory
SHELL = bash

default:
	@echo "Makefile for $(PACKAGE_NAME)"
	@echo
	@echo 'Usage:'
	@echo
	@echo '    make install    install the package in a virtual environment'
	@echo '    make reset      recreate the virtual environment'
	@echo '    make check      check coding style (PEP-8, PEP-257)'
	@echo '    make test       run the test suite, report coverage'
	@echo '    make tox        run the tests on all Python versions'
	@echo '    make readme     update usage in readme'
	@echo '    make docs       update documentation using Sphinx'
	@echo '    make publish    publish changes to GitHub/PyPI'
	@echo '    make clean      cleanup all temporary files'
	@echo

# The `virtualenv --system-site-packages' command is used to enable access to
# the python-apt binding which isn't available on PyPI (AFAIK) and so can't
# easily be installed inside of a Python virtual environment.

install:
	@test -d "$(VIRTUAL_ENV)" || mkdir -p "$(VIRTUAL_ENV)"
	@test -x "$(VIRTUAL_ENV)/bin/python" || virtualenv --python=$(PYTHON) --system-site-packages --quiet "$(VIRTUAL_ENV)"
	@test -x "$(VIRTUAL_ENV)/bin/pip" || easy_install pip
	@pip install --quiet --constraint=constraints.txt --requirement=requirements.txt
	@pip uninstall --yes $(PACKAGE_NAME) &>/dev/null || true
	@pip install --quiet --no-deps --ignore-installed .

reset:
	$(MAKE) clean
	rm -Rf "$(VIRTUAL_ENV)"
	$(MAKE) install

check: install
	@pip install --upgrade --quiet --constraint=constraints.txt --requirement=requirements-checks.txt
	@flake8

test: install
	@pip install --quiet --constraint=constraints.txt --requirement=requirements-tests.txt
	@py.test --cov
	@coverage html
	@coverage report --fail-under=90 &>/dev/null

full-coverage: install
	@pip install --quiet --constraint=constraints.txt --requirement=requirements-tests.txt
	@sudo "$(VIRTUAL_ENV)/bin/py.test" --cov
	@sudo chown --recursive --reference=. .
	@coverage report --fail-under=90 &>/dev/null

tox: install
	@pip install --quiet tox && tox

readme: install
	@pip install --quiet cogapp && cog.py -r README.rst

docs: readme
	@pip install --quiet sphinx
	@cd docs && sphinx-build -nb html -d build/doctrees . build/html

stdeb.cfg: install
	$(PYTHON) -c 'from deb_pkg_tools import generate_stdeb_cfg; generate_stdeb_cfg()' > stdeb.cfg

publish: stdeb.cfg
	git push origin && git push --tags origin
	$(MAKE) clean
	pip install --quiet twine wheel
	$(PYTHON) setup.py sdist bdist_wheel
	twine upload dist/*
	$(MAKE) clean

clean:
	@rm -Rf *.egg .cache .coverage .coverage.* .tox build dist docs/build htmlcov
	@find -depth -type d -name __pycache__ -exec rm -Rf {} \;
	@find -type f -name '*.pyc' -delete

.PHONY: default install reset check test tox readme docs stdeb.cfg publish clean
