.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f detectionengine-ruleset

shell:
	docker compose -f docker/docker-compose.yml exec detectionengine-ruleset bash

test:
	docker compose -f docker/docker-compose.yml exec detectionengine-ruleset pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec detectionengine-ruleset black .

lint:
	docker compose -f docker/docker-compose.yml exec detectionengine-ruleset flake8 .
