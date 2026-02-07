import os
import sys
import warnings

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

# Make app/ importable so `from service import ...` works
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

warnings.filterwarnings("ignore", category=DeprecationWarning)

from routers import search  # noqa: E402


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(search.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)
