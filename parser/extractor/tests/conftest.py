import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers.extractor import extractor_call_scope  # exact dependency

@pytest.fixture
def client():
    app.dependency_overrides[extractor_call_scope] = lambda: {"scope": "extractor:call"}  # bypass auth
    yield TestClient(app)
    app.dependency_overrides.clear()  # cleanup
