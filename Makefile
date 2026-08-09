PYTHON ?= $(shell command -v python3.12 2>/dev/null || command -v python3 2>/dev/null)
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
BASE_STAMP := $(VENV)/.base-installed
TEST_STAMP := $(VENV)/.test-installed

.PHONY: run test clean

$(BASE_STAMP): pyproject.toml
	@$(PYTHON) -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' || \
		{ echo 'Нужен Python 3.12. Укажите интерпретатор: make run PYTHON=/path/to/python3.12'; exit 1; }
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install -e .
	touch $(BASE_STAMP)

$(TEST_STAMP): $(BASE_STAMP) pyproject.toml
	$(VENV_PIP) install -e '.[test]'
	touch $(TEST_STAMP)

run: $(BASE_STAMP)
	$(VENV_PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test: $(TEST_STAMP)
	$(VENV_PYTHON) -m pytest

clean:
	rm -rf $(VENV)
