import os
import sys
import types
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

# -----------------------------
# Ensure bootstrap token exists
# -----------------------------
os.environ.setdefault("BOOTSTRAP_TOKEN", "test")

# -----------------------------
# MOCK security module EARLY
# -----------------------------
security_mock = types.ModuleType("security")
security_mock.hash_password = lambda p: "hashed-password"
security_mock.verify_password = lambda p, h: True
security_mock.create_access_token = lambda **kw: "access-token"
security_mock.create_service_token = lambda **kw: "service-token"

sys.modules["security"] = security_mock

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from routers import auth  # noqa: E402


class FakeMongo:
    def __init__(self):
        self.data = {
            "users": [],
            "service_accounts": [],
            "scopes": [],
            "audit_log": [],
        }

    def find(self, collection, query):
        return self.data.get(collection, [])

    def find_one(self, collection, query):
        for doc in self.data.get(collection, []):
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def insert_one(self, collection, doc):
        doc = dict(doc)
        doc["_id"] = f"{collection}-id"
        self.data.setdefault(collection, []).append(doc)
        return doc["_id"]

    def delete_one(self, collection, query):
        self.data[collection] = [
            d for d in self.data.get(collection, []) if d.get("_id") != query.get("_id")
        ]

    def update_one(self, collection, query, update):
        doc = self.find_one(collection, query)
        if not doc:
            return
        if "$set" in update:
            for k, v in update["$set"].items():
                doc[k] = v
        if "$pull" in update:
            for k, v in update["$pull"].items():
                doc[k] = [x for x in doc.get(k, []) if x not in v.get("$in", [])]

    def open_mongo_connection(self):
        return None, self

    def list_collection_names(self):
        return list(self.data.keys())

    def close_mongo_connection(self):
        pass


@pytest.fixture
def fake_mongo():
    return FakeMongo()


@pytest.fixture(autouse=True)
def override_mongo(fake_mongo):
    auth.get_mongo = lambda: fake_mongo


@pytest.fixture
def app():
    app = FastAPI()

    app.dependency_overrides[auth.user_auth.dependency] = lambda: {
        "email": "admin@test.com",
        "role": "admin",
    }
    app.dependency_overrides[auth.user_optional_auth.dependency] = lambda: {
        "email": "admin@test.com",
        "role": "admin",
    }
    app.dependency_overrides[auth.admin_auth.dependency] = lambda: {
        "email": "admin@test.com",
        "role": "admin",
    }

    app.include_router(auth.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)
