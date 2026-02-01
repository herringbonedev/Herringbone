# QA - Parser Extractor

This document defines the current QA state for the `parser/extractor` microservice.


## Scope

QA for Extractor focuses on **structural correctness** and **explicit API contracts**.

The goal is to ensure the service is testable, correctly packaged, and protected
against silent schema drift in its public API.


## Implemented Tests

### Unit - Boot Test

- Validates the service imports cleanly
- Enforces correct Python packaging and imports
- Catches missing dependencies and circular imports

Location:
```
tests/unit/test_boot.py
```


## Contract Tests

Extractor exposes a public parsing API whose response shape must remain stable.

Contract tests are used to **lock API behavior** and prevent unintentional
schema changes.

### Contract Coverage

Contract tests are defined for:

- `/parse` endpoint response schema
- Regex extraction output shape
- JSONPath extraction output shape
- Error response behavior

These tests assert:

- Required response fields
- Stable response types
- Consistent list vs scalar behavior

Contract tests are expected to fail if API responses drift.

Location:
```
tests/contract/
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

Only the unit boot test is required for structural QA.
Contract tests are added incrementally.


## Execution

Tests are executed locally using:

```bash
make test
```

Tests do not require Docker.


## Dependencies

- Runtime dependencies are defined in `requirements.txt`
- Internal shared modules are provided at runtime
- QA tooling is sourced from the repository root


## Current Status

- Structural QA complete
- Contract testing introduced to lock API schemas
- Behavioral and integration tests not yet enforced


## Ownership

QA for this service is owned by the Extractor microservice.