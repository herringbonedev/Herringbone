.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f logingestion-receiver

shell:
	docker compose -f docker/docker-compose.yml exec logingestion-receiver bash

test:
	docker compose -f docker/docker-compose.yml exec logingestion-receiver pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec logingestion-receiver black .

lint:
	docker compose -f docker/docker-compose.yml exec logingestion-receiver flake8 .
