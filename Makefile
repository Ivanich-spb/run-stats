PYTHON ?= python
RUNNER ?= ./run

.PHONY: install test run

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

run:
	$(RUNNER) --help
