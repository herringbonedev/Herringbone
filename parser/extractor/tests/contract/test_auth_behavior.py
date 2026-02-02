from fastapi.testclient import TestClient
from app.main import app

def test_parse_requires_auth(client):
    original_overrides = app.dependency_overrides.copy()

    try:
        # Remove auth override
        app.dependency_overrides = {}
        client = TestClient(app)

        response = client.post(
            "/parser/extractor/parse",
            json={
                "card": {"selector": "test"},
                "input": "example",
            },
        )

        assert response.status_code == 401

    finally:
        # Restore overrides so other tests are unaffected
        app.dependency_overrides = original_overrides
