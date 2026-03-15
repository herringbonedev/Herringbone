import sys
import types
import pytest
from fastapi.testclient import TestClient


# ----------------------------
# Mock security module early
# ----------------------------

security = types.ModuleType("app.security")

security.hash_password = lambda p: f"hashed-{p}"
security.verify_password = lambda p, h: h == f"hashed-{p}"

def create_access_token(**kwargs):
    return "test-access-token"

def create_service_token(**kwargs):
    return "test-service-token"

security.create_access_token = create_access_token
security.create_service_token = create_service_token

sys.modules["app.security"] = security


# ----------------------------
# Import app AFTER mocking
# ----------------------------

from app.main import app
from modules.auth import auth
import app.routers.auth as auth_router


# ----------------------------
# Fake Mongo
# ----------------------------

class FakeMongo:

    def __init__(self):
        self.collections = {
            "users": [],
            "service_accounts": [],
            "scopes": [],
            "audit_log": [],
        }

    def find(self, collection, query):
        return list(self.collections.get(collection, []))

    def find_one(self, collection, query):
        for doc in self.collections.get(collection, []):
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def insert_one(self, collection, doc):
        doc = doc.copy()
        doc["_id"] = str(len(self.collections[collection]) + 1)
        self.collections[collection].append(doc)
        return doc["_id"]

    def delete_one(self, collection, query):
        items = self.collections.get(collection, [])
        for i, doc in enumerate(items):
            if all(doc.get(k) == v for k, v in query.items()):
                items.pop(i)
                return True
        return False

    def update_one(self, collection, query, update):
        doc = self.find_one(collection, query)
        if not doc:
            return

        if "$pull" in update:
            for field, rule in update["$pull"].items():
                if field in doc and "$in" in rule:
                    doc[field] = [x for x in doc[field] if x not in rule["$in"]]

    def open_mongo_connection(self):
        return None, self

    def close_mongo_connection(self):
        pass

    def list_collection_names(self):
        return list(self.collections.keys())


# ----------------------------
# Mongo fixture
# ----------------------------

@pytest.fixture
def fake_mongo(monkeypatch):

    mongo = FakeMongo()

    # Override the router's get_mongo()
    monkeypatch.setattr(auth_router, "get_mongo", lambda: mongo)

    # Disable bootstrap token requirement
    monkeypatch.setattr(auth_router, "load_bootstrap_token", lambda: "test")

    return mongo


# ----------------------------
# Identity fixtures
# ----------------------------

@pytest.fixture
def admin_identity():
    return {
        "email": "admin@test.com",
        "scopes": ["*"],
    }


@pytest.fixture
def user_identity():
    return {
        "email": "user@test.com",
        "scopes": [
            "logs:read",
            "search:query",
            "incidents:read",
        ],
    }


# ----------------------------
# Test client
# ----------------------------

@pytest.fixture
def client(fake_mongo, admin_identity):

    app.dependency_overrides[auth.get_identity] = lambda: admin_identity

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()