.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f parser-cardset

shell:
	docker compose -f docker/docker-compose.yml exec parser-cardset bash

test:
	docker compose -f docker/docker-compose.yml exec parser-cardset pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec parser-cardset black .

lint:
	docker compose -f docker/docker-compose.yml exec parser-cardset flake8 .
