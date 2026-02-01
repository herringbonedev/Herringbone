# Testing Architecture in Herringbone

This document describes the **testing architecture and conventions** used in the Herringbone repository.
It intentionally avoids documenting individual test cases or test logic, which are owned by each microservice.

Service-specific testing plans and details live alongside the code in `QA.md` files within each microservice directory.

## Purpose

Testing in Herringbone exists to:

- Enforce correct Python packaging and imports
- Prevent Docker-only behavior from masking defects
- Keep microservices isolated and independently testable
- Establish a foundation for enterprise and compliance requirements

This document describes **how testing is structured**, not **what is tested**.

## Scope

Herringbone is a multi-service platform composed of independent Python microservices.
Each microservice is responsible for:

- Defining its own test coverage goals
- Documenting its test strategy in a local `QA.md`
- Maintaining tests that validate its behavior

The repository provides shared testing infrastructure and conventions.

## Test Structure Convention

All Python microservices follow the same directory structure:

```
tests/
├── unit/
├── contract/
├── component/
└── integration/
```

These directories define **test intent**, not execution guarantees.
Individual services may populate these directories incrementally.

## Execution Model

Tests are executed **locally**, outside of Docker, using a per-service virtual environment.

Each microservice exposes a standard entry point:

```bash
make test
```

The Makefile defines how tests are executed for that service.

Docker is not required to run tests.

---

## Dependency Model

Testing relies on a strict separation of dependency concerns.

### Runtime dependencies (per service)

Each microservice defines its runtime dependencies in:

```
requirements.txt
```

These dependencies are limited to PyPI packages required for service execution.

---

### Internal shared code (runtime only)

Shared internal code lives in:

```
modules/
```

This code is mounted or copied into containers at runtime.
It is not installed locally as a pip dependency.

---

### Dev / QA tooling (repo-wide)

All test and QA tooling is defined once at the repository root:

```
requirements-dev.txt
```

This includes tooling such as pytest, formatters, and linters.
Microservices consume this tooling via their Makefiles.

## Python Packaging Rules

All Python services follow consistent packaging rules:

- Application code lives in an `app/` package
- `__init__.py` files are present
- Imports are absolute and package-based

These rules ensure that tests behave consistently in local and containerized environments.

## Configuration Ownership

Testing behavior is centralized at the repository root:

- `pyproject.toml` - formatting, linting, pytest configuration
- `requirements-dev.txt` - pinned QA tooling
- `pytest.ini` - standardized pytest configuration
- `.gitignore` - excludes test artifacts and local environments

Microservices do not define their own QA tool configuration.

## Service-Level Testing Documentation

Each microservice must include a:

```
QA.md
```

This file documents:

- Test intent and scope
- Coverage expectations
- Contract assumptions
- Known limitations

Testing plans are owned by the service, not the platform.

## Current State

- Test scaffolding is established across services
- Boot-level validation exists to enforce correct packaging
- Infrastructure is in place for incremental test expansion

Testing is intentionally **foundational**, not exhaustive.

## Guiding Principle

> The platform defines how tests run.
> Each service defines what correctness means.