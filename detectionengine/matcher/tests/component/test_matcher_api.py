from fastapi import FastAPI
from fastapi.testclient import TestClient

from detectionengine.matcher.app.routers.matcher import router, run_matchengine


def test_find_match_happy_path():
    app = FastAPI()
    
    app.dependency_overrides[run_matchengine] = lambda: {
        "scope": "detectionengine:run"
    }

    app.include_router(router)
    client = TestClient(app)

    r = client.post(
        "/detectionengine/matcher/find_match",
        json={
            "rule": {"regex": "hello", "key": "raw"},
            "log_data": {"raw": "hello world"},
        },
    )

    assert r.status_code == 200

    body = r.json()
    assert body["matched"] is True
    assert body["details"] == "Regex evaluated successfully"
