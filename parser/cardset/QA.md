# QA - Parser CardSet

This document defines the current QA state for the `parser/cardset` microservice.

## Scope

QA for CardSet currently focuses on **structural correctness**, not behavioral validation.

The goal is to ensure the service is testable, correctly packaged, and free of
Docker-only assumptions.

## Implemented Tests

### Unit - Boot Test

- Validates the service imports cleanly
- Enforces correct Python packaging and imports
- Catches missing dependencies and circular imports

Location:
```
tests/unit/test_boot.py
```

## Test Structure

The following test directories exist to define intent:

```
tests/
├── unit/
├── contract/
├── component/
└── integration/
```

Only the unit boot test is implemented at this time.

## Execution

Tests are executed locally using:

```bash
make test
```

Tests do not require Docker.

## Dependencies

- Runtime dependencies are defined in `requirements.txt` and `requirements-internal.txt`
- Shared internal modules are provided at runtime
- QA tooling is sourced from the repository root

## Current Status

- Structural QA complete
- Service is importable and testable
- No behavioral or contract tests implemented yet

## Ownership

QA for this service is owned by the CardSet microservice.