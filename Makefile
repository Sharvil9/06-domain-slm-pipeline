PYTHON ?= python3

.PHONY: check test demo
check:
	$(PYTHON) -m compileall -q src tests
	$(PYTHON) -m unittest discover -s tests -v

test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	PYTHONPATH=src $(PYTHON) -m domain_slm --config configs/sample.toml --output outputs/sample
