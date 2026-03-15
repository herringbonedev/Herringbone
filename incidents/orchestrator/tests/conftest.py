import warnings
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers import orchestrator

warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture
def fake_identity():
    return {
        "type": "service",
        "service": "test-orchestrator",
        "service_id": "svc-test",
        "scopes": ["incidents:orchestrate"],
        "context_id": "default",
    }


@pytest.fixture
def app(monkeypatch, fake_identity):
    app = FastAPI()
    app.include_router(orchestrator.router)

    # override auth dependency
    app.dependency_overrides[orchestrator.orchestrator_run] = lambda: fake_identity

    # mock service token
    monkeypatch.setattr(orchestrator, "_service_token_cache", "token")

    return app


@pytest.fixture
def client(app):
    return TestClient(app)