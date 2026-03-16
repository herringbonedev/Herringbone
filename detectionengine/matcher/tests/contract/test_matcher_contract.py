from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth.auth import get_identity
from detectionengine.matcher.app.routers.matcher import router


def test_response_contract_shape():
    app = FastAPI()

    app.dependency_overrides[get_identity] = lambda: {
        "type": "service",
        "service": "pytest",
        "service_id": "matcher-test",
        "scopes": ["detectionengine:run"],
        "context_id": "default",
    }

    app.include_router(router)

    client = TestClient(app)

    r = client.post(
        "/detectionengine/matcher/find_match",
        json={
            "rule": {"regex": "hello"},
            "log_data": {"raw": "hello"},
        },
    )

    assert r.status_code == 200