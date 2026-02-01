# Parser Extractor Service

The extractor service applies regex and JSONPath extraction logic to input data based on a provided card definition.

It is a pure processing service and does not persist state.

## Responsibilities

The extractor service:

Processes structured or unstructured input
Applies regex selectors when defined
Applies JSONPath selectors when defined
Returns a normalized extraction result
Enforces authenticated, scoped access

## API

POST /parser/extractor/parse

The parse endpoint accepts a card definition and an input payload, then returns extracted results in a stable response shape.

Authentication is required and enforced via service scope.

## Response Contract

Successful responses always include a top level results object.

Errors related to JSONPath evaluation are returned as structured data within the results object rather than failing the request.

Invalid request payloads are rejected with a 422 response.

## Testing

This service uses contract tests to enforce API behavior and prevent schema drift.

Tests cover:

Authentication enforcement
Response schema stability
Regex output shape
JSONPath output shape
Error response behavior

All tests must pass before changes are merged.

## Running Tests

Run tests locally using the Makefile:

make test

## Notes

This service intentionally avoids side effects and database access.
All externally visible behavior is enforced through tests.
