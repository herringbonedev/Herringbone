.PHONY: up down rebuild logs test venv clean-venv

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f parser-enrichment

venv:
	python3 -m venv $(VENV)

test: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r ../../requirements-dev.txt
	PYTHONPATH=../../modules $(PYTHON) -m pytest

clean-venv:
	rm -rf $(VENV)
