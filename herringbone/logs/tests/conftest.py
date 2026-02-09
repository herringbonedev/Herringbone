import os
import sys
import warnings
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

warnings.filterwarnings("ignore", category=DeprecationWarning)

from routers import logs  # noqa: E402


class FakeMongo:
    def __init__(self):
        self.data = {
            "events": [],
            "event_state": [],
            "parse_results": [],
            "detections": [],
            "incidents": [],
        }

    def find(self, collection, filter_query):
        return self.data.get(collection, [])

    def find_one(self, collection, filter_query):
        items = self.data.get(collection, [])
        return items[0] if items else None

    def find_sorted(self, collection, filter_query, sort, limit):
        return self.data.get(collection, [])[:limit]


@pytest.fixture
def fake_mongo():
    return FakeMongo()


@pytest.fixture(autouse=True)
def override_mongo(fake_mongo):
    logs.get_mongo = lambda: fake_mongo


@pytest.fixture
def app():
    app = FastAPI()

    app.dependency_overrides[logs.events_get_auth.dependency] = lambda: {"sub": "test"}
    app.dependency_overrides[logs.user_auth.dependency] = lambda: {"sub": "test"}

    app.include_router(logs.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)
