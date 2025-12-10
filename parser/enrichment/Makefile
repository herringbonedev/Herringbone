.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f parser-enrichment

shell:
	docker compose -f docker/docker-compose.yml exec parser-enrichment bash

test:
	docker compose -f docker/docker-compose.yml exec parser-enrichment pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec parser-enrichment black .

lint:
	docker compose -f docker/docker-compose.yml exec parser-enrichment flake8 .
