.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f incidents-incidentset

shell:
	docker compose -f docker/docker-compose.yml exec incidents-incidentset bash

test:
	docker compose -f docker/docker-compose.yml exec incidents-incidentset pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec incidents-incidentset black .

lint:
	docker compose -f docker/docker-compose.yml exec incidents-incidentset flake8 .
