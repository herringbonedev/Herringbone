# Herringbone Project Standards & Conventions

These are the core standards for the Herringbone project

### Folder structure

A **Unit** has a folder at the root of the repository. It's **Elements** are subdirectories within.

Example:
```
.
├── detectionengine     # <------ Unit
│   ├── detector        # <------ Element
│   ├── matcher         # <------ Element
```

The **Element** directory is the name of the microservice. All of that microservices code lives within the **Element* directory.

A microservice **Element** directory follows this structure.

Example:
```
.
├── detectionengine
│   ├── detector
│   │   ├── app
│   │   │   ├── modules
│   │   ├── docker
```

### Required building / testing components

You must include a **Makefile** in the root of the **Element** microservice directory. This is intended
to be the docker-compose controller.

Use the following template for your **Makefile**:
```
.PHONY: up down rebuild logs shell test fmt lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down -v

rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache

logs:
	docker compose -f docker/docker-compose.yml logs -f <microservice name>

shell:
	docker compose -f docker/docker-compose.yml exec <microservice name> bash

test:
	docker compose -f docker/docker-compose.yml exec <microservice name> pytest -q

fmt:
	docker compose -f docker/docker-compose.yml exec <microservice name> black .

lint:
	docker compose -f docker/docker-compose.yml exec <microservice name> flake8 .
```

The docker-compose.yml and all of it's dependencies (like init-mongo.js) should live inside of the **docker** directory.

For now dependencies like **requirements.txt** are to live at the root of the **Element** directory.

Example:
```
├── detectionengine
│   ├── detector
│   │   ├── app
│   │   │   ├── main.py
│   │   │   ├── modules
│   │   │   │   └── database
│   │   │   │       ├── __init__.py
│   │   │   │       └── mongo_db.py
│   │   ├── docker
│   │   │   ├── docker-compose.yml
│   │   │   ├── Dockerfile
│   │   │   └── init-mongo.js
│   │   ├── Makefile
│   │   └── requirements.txt
```

### Milestones, Issues, and Projects

Herringbone uses **Milestones** as Epics to deliver new features.

An Issue tickets double as feature tickets when linked to a **Milestone**

**Milestones** MUST:
- Have a start and end date
- Provide a high-level description of the feature or capability delivered
- Contain at least 1 Issue

**Issues** MUST:
- Have a Type (Bug, Feature, Task)
- Include any possible relevant labels (ci, cd, parser, etc.)
- Have a clear expected outcome
- Follow the Issue template

```
Description:

Some description that assists in giving clear context to help complete the issue.

Expected outcome:

Some clear expected outcome for the issue.
```

### API routing standards

API Routes must follow the routing standards.

All routes must be prefixed with the **Unit** name then the **Element** name.

Example:
```
/parser/cardset/update_card
```

**Unit**: Parser
**Element**: CardSet
**Route**: update_card