.PHONY: test venv clean-venv

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

venv:
	python3 -m venv $(VENV)

test: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r cardset/requirements.txt
	$(PIP) install -r extractor/requirements.txt
	$(PIP) install -r enrichment/requirements.txt
	$(PIP) install -r ../requirements-dev.txt
	PYTHONPATH=cardset:extractor:enrichment:../modules \
	$(PYTHON) -m pytest -q tests/smoke

clean-venv:
	rm -rf $(VENV)
