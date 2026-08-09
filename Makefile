PYTHON := python3.12
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: run test clean

$(VENV)/.installed: pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install -e '.[test]'
	touch $(VENV)/.installed

run: $(VENV)/.installed
	$(VENV_PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test: $(VENV)/.installed
	$(VENV_PYTHON) -m pytest

clean:
	rm -rf $(VENV)