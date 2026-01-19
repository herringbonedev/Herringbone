.PHONY: up down rebuild search shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f herringbone-search

shell:
	docker compose -f docker/docker-compose.yml exec herringbone-search bash

test:
	docker compose -f docker/docker-compose.yml exec herringbone-search pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec herringbone-search black .

lint:
	docker compose -f docker/docker-compose.yml exec herringbone-search flake8 .
