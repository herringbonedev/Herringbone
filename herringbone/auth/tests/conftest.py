import os
import sys
import types
from datetime import datetime, UTC
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make test auth deterministic before app import.
os.environ.setdefault("BOOTSTRAP_TOKEN", "test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SERVICE_JWT_PRIVATE_KEY", "test-private-key")
os.environ.setdefault("SERVICE_JWT_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("MONGO_USER", "test")
os.environ.setdefault("MONGO_PASS", "test")
os.environ.setdefault("MONGO_HOST", "localhost")
os.environ.setdefault("MONGO_PORT", "27017")
os.environ.setdefault("DB_NAME", "herringbone")
os.environ.setdefault("AUTH_DB", "admin")


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, name, fake):
        self.name = name
        self.fake = fake

    def find(self, query=None, *args, **kwargs):
        return self.fake.find_with_context(self.name, query or {}, context_id=query.get("context_id") if query else "default")

    def find_one(self, query=None, *args, **kwargs):
        return self.fake.find_one_with_context(self.name, query or {}, context_id=query.get("context_id") if query else "default")

    def insert_one(self, doc):
        inserted_id = self.fake.insert_one(self.name, doc, context_id=doc.get("context_id", "default"))
        return FakeInsertResult(inserted_id)

    def update_one(self, query, update, *args, **kwargs):
        return self.fake.update_one(self.name, query, update, context_id=query.get("context_id", "default"))

    def delete_one(self, query, *args, **kwargs):
        return self.fake.delete_one(self.name, query, context_id=query.get("context_id", "default"))

    def count_documents(self, query=None, *args, **kwargs):
        return len(self.find(query or {}))


class FakeMongoDBHandle:
    def __init__(self, fake):
        self.fake = fake

    def __getitem__(self, collection):
        return FakeCollection(collection, self.fake)

    def command(self, command_name):
        return {"ok": 1}

    def list_collection_names(self):
        return list(self.fake.store.keys())


class FakeMongoClient:
    def __init__(self, fake):
        self.fake = fake
        self.admin = FakeMongoDBHandle(fake)

    def __getitem__(self, database):
        return FakeMongoDBHandle(self.fake)

    def close(self):
        return None


class FakeMongo:
    store = {
        "users": [],
        "service_accounts": [],
        "audit_log": [],
        "ingestion_keys": [],
        "organizations": [
            {
                "_id": "default-org",
                "slug": "default",
                "name": "Default",
                "status": "active",
                "context_id": "default",
            }
        ],
    }

    def __init__(self, *args, **kwargs):
        pass

    def open_mongo_connection(self):
        return FakeMongoClient(self), FakeMongoDBHandle(self)

    def close_mongo_connection(self, *args, **kwargs):
        return None

    @staticmethod
    def _matches(doc, query):
        for key, value in (query or {}).items():
            if key == "_id":
                if str(doc.get("_id")) != str(value):
                    return False
                continue

            if isinstance(value, dict):
                if "$ne" in value and doc.get(key) == value["$ne"]:
                    return False
                if "$in" in value and doc.get(key) not in value["$in"]:
                    return False
                continue

            if doc.get(key) != value:
                return False

        return True

    def find_with_context(self, collection, query=None, context_id="default", *args, **kwargs):
        query = dict(query or {})
        context_id = context_id or "default"

        rows = []
        for doc in self.store.setdefault(collection, []):
            if doc.get("context_id", "default") != context_id:
                continue
            if self._matches(doc, query):
                rows.append(dict(doc))
        return rows

    def find_one_with_context(self, collection, query=None, context_id="default", *args, **kwargs):
        rows = self.find_with_context(collection, query or {}, context_id=context_id)
        return rows[0] if rows else None

    def insert_one(self, collection, document, context_id="default", *args, **kwargs):
        doc = dict(document)
        doc.setdefault("_id", f"{collection}-{len(self.store.setdefault(collection, [])) + 1}")
        doc.setdefault("context_id", context_id or "default")
        doc.setdefault("created_at", datetime.now(UTC))
        self.store.setdefault(collection, []).append(doc)
        return doc["_id"]

    def update_one(self, collection, query, update, context_id="default", *args, **kwargs):
        for doc in self.store.setdefault(collection, []):
            if doc.get("context_id", "default") == (context_id or "default") and self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                else:
                    doc.update(update)
                return {"matched_count": 1, "modified_count": 1}
        return {"matched_count": 0, "modified_count": 0}

    def delete_one(self, collection, query, context_id="default", *args, **kwargs):
        rows = self.store.setdefault(collection, [])
        for i, doc in enumerate(rows):
            if doc.get("context_id", "default") == (context_id or "default") and self._matches(doc, query):
                del rows[i]
                return {"deleted_count": 1}
        return {"deleted_count": 0}


class FakeAuditLogger:
    def __init__(self, *args, **kwargs):
        pass

    def log(self, *args, **kwargs):
        return None


def _token(payload=None):
    return "test-token"


def create_access_token(*args, **kwargs):
    return _token()


def create_context_token(*args, **kwargs):
    return "test-context-token"


def create_service_token(*args, **kwargs):
    return "test-service-token"

def generate_ingestion_key(*args, **kwargs):
    return "hb_ingest_test_key"


def hash_ingestion_key(key):
    return f"hashed:{key}"


def verify_ingestion_key(key, hashed):
    return hashed == f"hashed:{key}" or key == "hb_ingest_test_key"


def verify_password(plain_password, hashed_password):
    return True


def hash_password(password):
    return f"hashed:{password}"


# Some auth tests run without the real app.security module fully available.
security = types.ModuleType("app.security")
security.create_access_token = create_access_token
security.create_context_token = create_context_token
security.create_service_token = create_service_token
security.generate_ingestion_key = generate_ingestion_key
security.hash_ingestion_key = hash_ingestion_key
security.verify_ingestion_key = verify_ingestion_key
security.verify_password = verify_password
security.hash_password = hash_password
security.decode_token = lambda token: {"sub": "test", "email": "admin@example.com", "scope": ["*"], "context_id": "default"}
security.decode_service_token = lambda token: {"sub": "svc", "service": "test", "scope": ["*"], "context_id": "default"}
sys.modules["app.security"] = security


from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def patch_database(monkeypatch):
    # Reset for each test, while keeping default org.
    FakeMongo.store = {
        "users": [],
        "service_accounts": [],
        "audit_log": [],
        "ingestion_keys": [],
        "organizations": [
            {
                "_id": "default-org",
                "slug": "default",
                "name": "Default",
                "status": "active",
                "context_id": "default",
            }
        ],
    }

    # Patch direct router helpers.
    for module_name in (
        "app.routers.auth",
        "app.routers.users",
        "app.routers.services",
        "app.routers.ingestion",
    ):
        try:
            module = __import__(module_name, fromlist=["dummy"])
        except Exception:
            continue

        if hasattr(module, "get_mongo"):
            monkeypatch.setattr(module, "get_mongo", lambda: FakeMongo(), raising=False)

        if hasattr(module, "get_audit_logger"):
            monkeypatch.setattr(module, "get_audit_logger", lambda: FakeAuditLogger(), raising=False)

        if hasattr(module, "HerringboneMongoDatabase"):
            monkeypatch.setattr(module, "HerringboneMongoDatabase", FakeMongo, raising=False)

        if hasattr(module, "AuditLogger"):
            monkeypatch.setattr(module, "AuditLogger", FakeAuditLogger, raising=False)

        if hasattr(module, "load_bootstrap_token"):
            monkeypatch.setattr(module, "load_bootstrap_token", lambda: "test", raising=False)
        if hasattr(module, "get_identity"):
            monkeypatch.setattr(
                module,
                "get_identity",
                lambda: {"type": "user", "email": "admin@example.com", "scopes": ["*"], "context_id": "default"},
                raising=False,
            )

        if hasattr(module, "get_context"):
            monkeypatch.setattr(
                module,
                "get_context",
                lambda: {
                    "identity": {"type": "user", "email": "admin@example.com", "scopes": ["*"], "context_id": "default"},
                    "context_id": "default",
                    "scopes": ["*"],
                },
                raising=False,
            )

        if hasattr(module, "require_scopes"):
            monkeypatch.setattr(module, "require_scopes", lambda *scopes: (lambda context=None: True), raising=False)

    # Patch the shared DB class too, for routes that instantiate it directly.
    try:
        import modules.database.mongo_db as mongo_db
        monkeypatch.setattr(mongo_db, "HerringboneMongoDatabase", FakeMongo, raising=False)
    except Exception:
        pass

    yield


def _fake_identity():
    return {
        "type": "user",
        "sub": "test-user",
        "user_id": "test-user",
        "email": "admin@example.com",
        "scopes": ["*"],
        "scope": ["*"],
        "context_id": "default",
    }


def _fake_context():
    identity = _fake_identity()
    return {
        "identity": identity,
        "context_id": "default",
        "scopes": ["*"],
        "scope": ["*"],
    }


@pytest.fixture
def client():
    # Override real auth dependencies so component tests do not decode JWTs.
    try:
        import modules.auth.auth as auth_deps

        app.dependency_overrides[auth_deps.get_identity] = _fake_identity
        app.dependency_overrides[auth_deps.get_context] = _fake_context
    except Exception:
        pass

    # Also override any same-named dependency objects imported into routers.
    for module_name in (
        "app.routers.auth",
        "app.routers.users",
        "app.routers.services",
        "app.routers.ingestion",
    ):
        try:
            module = __import__(module_name, fromlist=["dummy"])
        except Exception:
            continue

        if hasattr(module, "get_identity"):
            app.dependency_overrides[module.get_identity] = _fake_identity

        if hasattr(module, "get_context"):
            app.dependency_overrides[module.get_context] = _fake_context

    return TestClient(app)


@pytest.fixture
def fake_mongo():
    return FakeMongo()