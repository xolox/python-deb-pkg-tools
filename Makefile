# Makefile for deb-pkg-tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: May 25, 2014
# URL: https://github.com/xolox/python-deb-pkg-tools

WORKON_HOME ?= $(HOME)/.virtualenvs
VIRTUAL_ENV ?= $(WORKON_HOME)/deb-pkg-tools

default:
	@echo 'Makefile for deb-pkg-tools'
	@echo
	@echo 'Usage:'
	@echo
	@echo '    make install    install the package in a virtual environment'
	@echo '    make reset      recreate the virtual environment'
	@echo '    make test       run the test suite'
	@echo '    make coverage   run the tests, report coverage'
	@echo '    make docs       update documentation using Sphinx'
	@echo '    make publish    publish changes to GitHub/PyPI'
	@echo '    make clean      cleanup all temporary files'
	@echo

install:
	test -d "$(VIRTUAL_ENV)" || virtualenv --system-site-packages "$(VIRTUAL_ENV)"
	test -x "$(VIRTUAL_ENV)/bin/pip"       || (. "$(VIRTUAL_ENV)/bin/activate" && easy_install pip)
	test -x "$(VIRTUAL_ENV)/bin/pip-accel" || (. "$(VIRTUAL_ENV)/bin/activate" && pip install pip-accel)
	. "$(VIRTUAL_ENV)/bin/activate" && pip-accel install -r requirements.txt
	. "$(VIRTUAL_ENV)/bin/activate" && pip uninstall -y deb-pkg-tools || true
	. "$(VIRTUAL_ENV)/bin/activate" && pip install --no-deps --editable .

reset:
	rm -Rf "$(VIRTUAL_ENV)"
	make --no-print-directory install

doctest: install
	"$(VIRTUAL_ENV)/bin/python" check_doctest_examples.py

test: install doctest
	"$(VIRTUAL_ENV)/bin/python" setup.py test

coverage: install
	test -x "$(VIRTUAL_ENV)/bin/coverage"  || (. "$(VIRTUAL_ENV)/bin/activate" && pip-accel install coverage)
	. "$(VIRTUAL_ENV)/bin/activate" && coverage run --source=deb_pkg_tools setup.py test
	. "$(VIRTUAL_ENV)/bin/activate" && coverage html
	if [ "`whoami`" != root ] && which gnome-open >/dev/null 2>&1; then gnome-open htmlcov/index.html; fi

clean:
	rm -Rf *.egg *.egg-info .coverage build dist docs/build htmlcov
	find -depth -type d -name __pycache__ -exec rm -Rf {} \;
	find -type f -name '*.pyc' -delete

docs: install
	. "$(VIRTUAL_ENV)/bin/activate" && pip-accel install sphinx
	cd docs && make html
	if which gnome-open >/dev/null 2>&1; then \
		gnome-open "docs/build/html/index.html"; \
	fi

publish: stdeb.cfg
	git push origin && git push --tags origin
	make clean && python setup.py sdist upload

stdeb.cfg:
	python -c 'from deb_pkg_tools import generate_stdeb_cfg; generate_stdeb_cfg()' > stdeb.cfg

.PHONY: default install reset test coverage clean docs publish stdeb.cfg
