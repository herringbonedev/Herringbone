.PHONY: test venv clean-venv

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

venv:
	python3 -m venv $(VENV)

test: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r correlator/requirements.txt
	$(PIP) install -r incidentset/requirements.txt
	$(PIP) install -r orchestrator/requirements.txt
	$(PIP) install -r ../requirements-dev.txt
	PYTHONPATH=correlator/app:incidentset/app:orchestrator/app:../modules \
	$(PYTHON) -m pytest -q tests

clean-venv:
	rm -rf $(VENV)
