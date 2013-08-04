# Makefile for deb-pkg-tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: August 4, 2013
# URL: https://github.com/xolox/python-deb-pkg-tools

VIRTUAL_ENV = $(HOME)/.virtualenvs/deb-pkg-tools

default:
	@echo 'Makefile for deb-pkg-tools'
	@echo
	@echo 'Usage:'
	@echo
	@echo '    make test       run the test suite'
	@echo '    make coverage   run the tests, report coverage'
	@echo '    make docs       update documentation using Sphinx'
	@echo '    make publish    publish changes to GitHub/PyPI'
	@echo '    make clean      cleanup all temporary files'
	@echo

test:
	python setup.py test

coverage:
	test -d $(VIRTUAL_ENV) || virtualenv $(VIRTUAL_ENV)
	test -x $(VIRTUAL_ENV)/bin/pip-accel || $(VIRTUAL_ENV)/bin/pip install pip-accel
	test -x $(VIRTUAL_ENV)/bin/coverage || $(VIRTUAL_ENV)/bin/pip-accel install coverage
	$(VIRTUAL_ENV)/bin/pip uninstall -y deb-pkg-tools || true
	$(VIRTUAL_ENV)/bin/pip-accel install -r requirements.txt
	$(VIRTUAL_ENV)/bin/pip install .
	$(VIRTUAL_ENV)/bin/coverage run --include='*deb_pkg_tools*' deb_pkg_tools/tests.py
	$(VIRTUAL_ENV)/bin/coverage html
	$(VIRTUAL_ENV)/bin/coverage report -m
	if [ "`whoami`" != root ]; then gnome-open htmlcov/index.html; fi

clean:
	rm -Rf *.egg *.egg-info .coverage build dist docs/build htmlcov

docs:
	cd docs && make html
	if which gnome-open >/dev/null 2>&1; then \
		gnome-open "docs/build/html/index.html"; \
	fi

publish:
	git push origin && git push --tags origin
	make clean && python setup.py sdist upload

.PHONY: docs
