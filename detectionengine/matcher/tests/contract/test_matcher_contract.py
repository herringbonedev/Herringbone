from fastapi import FastAPI
from fastapi.testclient import TestClient

from detectionengine.matcher.app.routers.matcher import router, run_matchengine


def test_response_contract_shape():
    app = FastAPI()
    
    app.dependency_overrides[run_matchengine] = lambda: {
        "scope": "detectionengine:run"
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

    body = r.json()
    assert set(body.keys()) == {
        "matched",
        "details",
        "rule",
        "log_data",
    }
