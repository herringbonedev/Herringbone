import os
import pytest
from fastapi.testclient import TestClient
from testcontainers.mongodb import MongoDbContainer
from urllib.parse import urlparse
from pymongo import MongoClient
from pymongo.errors import OperationFailure

from modules.auth.auth import get_identity

from app.main import app
from app.routers.cardset import (
    get_mongo,
    cardset_write,
    cardset_read,
)


class FakeMongo:
    store = []

    def __init__(self):
        pass

    @staticmethod
    def _get_nested(doc, dotted_key):
        value = doc
        for part in dotted_key.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    @classmethod
    def _matches(cls, doc, query):
        for key, expected in (query or {}).items():
            actual = cls._get_nested(doc, key) if "." in key else doc.get(key)

            if isinstance(expected, dict):
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                continue

            if actual != expected:
                return False

        return True

    def find_one(self, collection, query=None, *args, **kwargs):
        return self.find_one_with_context(
            collection,
            query or {},
            context_id=kwargs.get("context_id", "default"),
        )

    def find(self, collection, query=None, *args, **kwargs):
        return self.find_with_context(
            collection,
            query or {},
            context_id=kwargs.get("context_id", "default"),
            limit=kwargs.get("limit"),
        )

    def find_one_with_context(self, collection, query=None, context_id="default", *args, **kwargs):
        rows = self.find_with_context(collection, query or {}, context_id=context_id, limit=1)
        return rows[0] if rows else None

    def find_with_context(self, collection, query=None, context_id="default", limit=None, *args, **kwargs):
        rows = []
        for doc in self.store:
            if doc.get("_collection") != collection:
                continue
            if doc.get("context_id", "default") != (context_id or "default"):
                continue
            if self._matches(doc, query or {}):
                rows.append(dict(doc))
                if limit and len(rows) >= limit:
                    break
        return rows

    def insert_one(self, collection, document, context_id="default", *args, **kwargs):
        doc = dict(document)
        doc.setdefault("_id", f"fake-{len(self.store) + 1}")
        doc.setdefault("_collection", collection)
        doc.setdefault("context_id", context_id or "default")
        self.store.append(doc)
        return doc["_id"]

    def upsert_one(self, collection, filter_query, update, context_id="default", *args, **kwargs):
        for doc in self.store:
            if doc.get("_collection") == collection and doc.get("context_id", "default") == (context_id or "default") and self._matches(doc, filter_query):
                doc.update(update)
                return doc.get("_id", "fake_id")

        doc = dict(update)
        doc.setdefault("_id", f"fake-{len(self.store) + 1}")
        doc.setdefault("_collection", collection)
        doc.setdefault("context_id", context_id or "default")

        # Preserve selector fields from dotted filter queries for simple test readbacks.
        if "selector.type" in filter_query or "selector.value" in filter_query:
            doc.setdefault("selector", {})
            if "selector.type" in filter_query:
                doc["selector"]["type"] = filter_query["selector.type"]
            if "selector.value" in filter_query:
                doc["selector"]["value"] = filter_query["selector.value"]

        self.store.append(doc)
        return doc["_id"]


def override_mongo():
    return FakeMongo()


def fake_write_identity():
    return {
        "type": "user",
        "id": "test-user",
        "email": "test@local",
        "scopes": [
            "parser:cards:write",
            "parser:cards:read",
        ],
        "context_id": "default",
    }


def fake_read_identity():
    return {
        "type": "service",
        "service": "test-service",
        "service_id": "svc-test",
        "scopes": [
            "parser:cards:read",
        ],
        "context_id": "default",
    }


@pytest.fixture(scope="session")
def mongo_container():
    container = MongoDbContainer("mongo:7")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def integration_mongo_env(mongo_container):
    url = mongo_container.get_connection_url()
    parsed = urlparse(url)

    host = f"{parsed.hostname}:{parsed.port}"
    db_name = "herringbone"
    hb_user = "herringbone_test"
    hb_pass = "herringbone_test"

    if parsed.username and parsed.password:
        admin_uri = f"mongodb://{parsed.username}:{parsed.password}@{host}/admin"
        client = MongoClient(admin_uri, serverSelectionTimeoutMS=5000)

        try:
            client.admin.command("ping")
            db = client[db_name]

            try:
                db.command(
                    "createUser",
                    hb_user,
                    pwd=hb_pass,
                    roles=[{"role": "readWrite", "db": db_name}],
                )
            except OperationFailure as e:
                if getattr(e, "code", None) != 51003:
                    raise

        finally:
            client.close()

        os.environ["MONGO_USER"] = hb_user
        os.environ["MONGO_PASS"] = hb_pass
    else:
        os.environ["MONGO_USER"] = ""
        os.environ["MONGO_PASS"] = ""

    os.environ["MONGO_HOST"] = host
    os.environ["DB_NAME"] = db_name
    os.environ["COLLECTION_NAME"] = "cards"

    yield


@pytest.fixture
def client(request, mongo_container):

    is_integration = request.node.get_closest_marker("integration") is not None
    if not is_integration:
        FakeMongo.store = []

    # root auth override (required for require_context)
    app.dependency_overrides[get_identity] = fake_read_identity

    # router auth dependencies
    app.dependency_overrides[cardset_write] = fake_write_identity
    app.dependency_overrides[cardset_read] = fake_read_identity

    if is_integration:
        request.getfixturevalue("integration_mongo_env")
    else:
        app.dependency_overrides[get_mongo] = override_mongo

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()