.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f parser-extractor

shell:
	docker compose -f docker/docker-compose.yml exec parser-extractor bash

test:
	docker compose -f docker/docker-compose.yml exec parser-extractor pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec parser-extractor black .

lint:
	docker compose -f docker/docker-compose.yml exec parser-extractor flake8 .
