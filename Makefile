PYTHON ?= $(shell \
	for cmd in python3.12 python3.13 python3 python; do \
		path=$$(command -v $$cmd 2>/dev/null) || continue; \
		"$$path" -c 'import sys; sys.exit(sys.version_info[:2] < (3, 12))' >/dev/null 2>&1 \
			&& { echo "$$path"; break; }; \
	done)
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
BASE_STAMP := $(VENV)/.base-installed
TEST_STAMP := $(VENV)/.test-installed

.PHONY: run test clean

$(BASE_STAMP): pyproject.toml
	@test -n '$(PYTHON)' \
		&& $(PYTHON) -c 'import sys; sys.exit(sys.version_info[:2] < (3, 12))' 2>/dev/null || \
		{ echo 'Нужен Python 3.12+. Укажите интерпретатор: make run PYTHON=/path/to/python3.12'; exit 1; }
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
