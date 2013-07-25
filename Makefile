# Makefile for deb-pkg-tools.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: July 25, 2013
# URL: https://github.com/xolox/python-deb-pkg-tools

default:
	@echo 'Makefile for deb-pkg-tools'
	@echo
	@echo 'Usage:'
	@echo
	@echo '    make test       run the test suite'
	@echo '    make docs       update documentation using Sphinx'
	@echo '    make publish    publish changes to GitHub/PyPI'
	@echo '    make clean      cleanup all temporary files'
	@echo

test:
	python setup.py test

clean:
	rm -Rf build dist docs/build *.egg *.egg-info

docs:
	cd docs && make html
	if which gnome-open >/dev/null 2>&1; then \
		gnome-open "docs/build/html/index.html"; \
	fi

publish:
	git push origin && git push --tags origin
	make clean && python setup.py sdist upload

.PHONY: docs
