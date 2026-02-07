import warnings
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers import orchestrator

warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture
def app(monkeypatch):
    app = FastAPI()
    app.include_router(orchestrator.router)

    # override auth
    app.dependency_overrides[orchestrator.orchestrator_run] = (
        lambda: {"scope": "incidents:orchestrate"}
    )

    # mock service token
    monkeypatch.setattr(orchestrator, "_service_token_cache", "token")

    return app


@pytest.fixture
def client(app):
    return TestClient(app)
