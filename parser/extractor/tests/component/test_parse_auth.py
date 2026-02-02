
from fastapi.testclient import TestClient
from app.main import app

def test_parse_requires_auth():
    app.dependency_overrides = {}
    client = TestClient(app)
    r = client.post("/parser/extractor/parse", json={"card": {"selector": "x"}, "input": "y"})
    assert r.status_code == 401
