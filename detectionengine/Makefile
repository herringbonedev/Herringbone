.PHONY: test venv clean-venv

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

venv:
	python3 -m venv $(VENV)

test: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r detector/requirements.txt
	$(PIP) install -r matcher/requirements.txt
	$(PIP) install -r ruleset/requirements.txt
	$(PIP) install -r ../requirements-dev.txt
	PYTHONPATH=detector/app:detector:matcher:ruleset:../modules \
	$(PYTHON) -m pytest -q tests/smoke

clean-venv:
	rm -rf $(VENV)
