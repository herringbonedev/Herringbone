.PHONY: up down rebuild search shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f herringbone-auth

shell:
	docker compose -f docker/docker-compose.yml exec herringbone-auth bash

test:
	docker compose -f docker/docker-compose.yml exec herringbone-auth pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec herringbone-auth black .

lint:
	docker compose -f docker/docker-compose.yml exec herringbone-auth flake8 .
