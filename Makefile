# Makefile for deb-pkg-tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: July 16, 2015
# URL: https://github.com/xolox/python-deb-pkg-tools

WORKON_HOME ?= $(HOME)/.virtualenvs
VIRTUAL_ENV ?= $(WORKON_HOME)/deb-pkg-tools
ACTIVATE = . "$(VIRTUAL_ENV)/bin/activate"

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
	test -x "$(VIRTUAL_ENV)/bin/pip"       || ($(ACTIVATE) && easy_install pip)
	test -x "$(VIRTUAL_ENV)/bin/pip-accel" || ($(ACTIVATE) && pip install pip-accel)
	$(ACTIVATE) && pip-accel install -r requirements.txt
	$(ACTIVATE) && pip uninstall -y deb-pkg-tools || true
	$(ACTIVATE) && pip install --no-deps --editable .

reset:
	rm -Rf "$(VIRTUAL_ENV)"
	make --no-print-directory install

doctest: install
	$(ACTIVATE) && python check_doctest_examples.py

test: install doctest
	test -x "$(VIRTUAL_ENV)/bin/py.test" || ($(ACTIVATE) && pip-accel install pytest)
	$(ACTIVATE) && py.test --exitfirst --capture=no deb_pkg_tools/tests.py

coverage: install
	test -x "$(VIRTUAL_ENV)/bin/coverage" || ($(ACTIVATE) && pip-accel install coverage)
	$(ACTIVATE) && coverage run --source=deb_pkg_tools setup.py test
	$(ACTIVATE) && coverage html --omit=deb_pkg_tools/tests.py
	if [ "`whoami`" != root ] && which gnome-open >/dev/null 2>&1; then gnome-open htmlcov/index.html; fi

clean:
	rm -Rf *.egg *.egg-info .coverage build dist docs/build htmlcov
	find -depth -type d -name __pycache__ -exec rm -Rf {} \;
	find -type f -name '*.pyc' -delete

readme:
	test -x "$(VIRTUAL_ENV)/bin/cog.py" || ($(ACTIVATE) && pip-accel install cogapp)
	$(ACTIVATE) && cog.py -r README.rst

docs: install
	test -x "$(VIRTUAL_ENV)/bin/sphinx-build" || ($(ACTIVATE) && pip-accel install sphinx)
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
