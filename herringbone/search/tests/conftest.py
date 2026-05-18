import os
import sys
import warnings

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from modules.auth.auth import get_identity

# Make app/ importable so `from service import ...` works
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

warnings.filterwarnings("ignore", category=DeprecationWarning)

from routers import search  # noqa: E402


@pytest.fixture
def fake_identity():
    return {
        "type": "service",
        "service": "test",
        "service_id": "svc-test",
        "scopes": ["search:query", "search:schema"],
        "context_id": "default",
    }


@pytest.fixture
def app(fake_identity):
    app = FastAPI()

    # override root auth dependency
    app.dependency_overrides[get_identity] = lambda: fake_identity

    # override route-level scope dependencies when exported by the router
    search_query_auth = getattr(search, "search_query_auth", None)
    search_schema_auth = getattr(search, "search_schema_auth", None)

    if search_query_auth is not None:
        app.dependency_overrides[search_query_auth] = lambda: fake_identity

    if search_schema_auth is not None:
        app.dependency_overrides[search_schema_auth] = lambda: fake_identity

    app.include_router(search.router)

    return app


@pytest.fixture
def client(app):
    return TestClient(app)