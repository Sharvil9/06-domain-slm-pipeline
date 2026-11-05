PYTHON ?= python3

.PHONY: check test
check:
	$(PYTHON) -m compileall -q src tests
	$(PYTHON) -m unittest discover -s tests -v

test:
	$(PYTHON) -m unittest discover -s tests -v
