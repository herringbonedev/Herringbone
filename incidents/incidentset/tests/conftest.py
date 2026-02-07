import os
import sys
import warnings

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

# Make app/ importable so incidentset's `from schema import IncidentSchema` works.
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Silence datetime deprecations in tests only
warnings.filterwarnings("ignore", category=DeprecationWarning)

from routers import incidentset  # noqa: E402


class _FakeUpdateResult:
    def __init__(self):
        self.raw_result = {"ok": 1}


class _FakeCollection:
    def __init__(self):
        self.last_update_one = None
        self.result = _FakeUpdateResult()

    def update_one(self, flt, upd, upsert=False):
        self.last_update_one = {
            "filter": flt,
            "update": upd,
            "upsert": upsert,
        }
        return self.result


class _FakeDB:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = _FakeCollection()
        return self.collections[name]


class FakeMongo:
    def __init__(self):
        self.inserted = []
        self.docs = []
        self.one = None
        self.exc = None

        self._db = _FakeDB()
        self._client = object()
        self.opened = False
        self.closed = False

    def insert_one(self, collection, doc):
        if self.exc:
            raise self.exc
        self.inserted.append({"collection": collection, "doc": doc})

    def find(self, collection, query):
        if self.exc:
            raise self.exc
        return self.docs

    def find_one(self, collection, query):
        if self.exc:
            raise self.exc
        return self.one

    def open_mongo_connection(self):
        self.opened = True
        return self._client, self._db

    def close_mongo_connection(self):
        self.closed = True


@pytest.fixture
def fake_mongo():
    return FakeMongo()


@pytest.fixture
def app(fake_mongo):
    app = FastAPI()
    app.include_router(incidentset.router)

    # --- Mongo override ---
    app.dependency_overrides[incidentset.get_mongo] = lambda: fake_mongo

    # --- Auth overrides (IMPORTANT) ---
    # These must override the *variables*, not service_or_role(...)
    app.dependency_overrides[incidentset.incident_writer] = (
        lambda: {"scope": "incidents:write", "roles": ["admin"]}
    )
    app.dependency_overrides[incidentset.incident_reader] = (
        lambda: {"scope": "incidents:read", "roles": ["admin"]}
    )

    return app


@pytest.fixture
def client(app):
    return TestClient(app)
