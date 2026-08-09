.PHONY: run test

PYTHON ?= python

run:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	$(PYTHON) -m pytest
