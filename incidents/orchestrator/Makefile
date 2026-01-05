.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f incidents-orchestrator

shell:
	docker compose -f docker/docker-compose.yml exec incidents-orchestrator sh

test:
	docker compose -f docker/docker-compose.yml exec incidents-orchestrator pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec incidents-orchestrator black .

lint:
	docker compose -f docker/docker-compose.yml exec incidents-orchestrator flake8 .
