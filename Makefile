PYTHON ?= python3

.PHONY: check test demo doctor sql-demo
check:
	$(PYTHON) -m compileall -q src tests
	$(PYTHON) -m unittest discover -s tests -v

test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	PYTHONPATH=src $(PYTHON) -m domain_slm --config configs/sample.toml --output outputs/sample

doctor:
	PYTHONPATH=src $(PYTHON) -m domain_slm doctor

sql-demo:
	PYTHONPATH=src $(PYTHON) -m domain_slm prepare-sql --config configs/text2sql_sample.toml --output outputs/text2sql-sample
