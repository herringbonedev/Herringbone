from fastapi.testclient import TestClient
from app.main import app
from .conftest import PARSE_PATH


def test_parse_requires_auth():
    original_overrides = app.dependency_overrides.copy()

    try:
        # Remove auth override
        app.dependency_overrides = {}
        client = TestClient(app)

        response = client.post(
            PARSE_PATH,
            json={
                "card": {"selector": "test"},
                "input": "example",
            },
        )

        assert response.status_code == 401

    finally:
        # Restore overrides so other tests are unaffected
        app.dependency_overrides = original_overrides
