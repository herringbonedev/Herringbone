import os
import pytest
from fastapi.testclient import TestClient
from testcontainers.mongodb import MongoDbContainer
from urllib.parse import urlparse
from pymongo import MongoClient
from pymongo.errors import OperationFailure

from app.main import app
from app.routers.ruleset import (
    get_mongo,
    ruleset_write,
    ruleset_read,
    ruleset_admin,
)


# Fake Mongo for component tests
class FakeMongo:
    def __init__(self):
        self.rules = []

    def insert_one(self, collection, doc):
        self.rules.append(doc)

    def find(self, collection, query):
        return self.rules

    def find_one(self, collection, query):
        for r in self.rules:
            if r.get("_id") == query.get("_id"):
                return r
        return None

    def upsert_one(self, collection, query, doc, clean_codec=True):
        for i, r in enumerate(self.rules):
            if r.get("_id") == query.get("_id"):
                self.rules[i] = {**r, **doc}
                return
        self.rules.append({**query, **doc})


@pytest.fixture
def fake_mongo():
    return FakeMongo()


def override_mongo(fake_mongo):
    return fake_mongo


# Fake auth payload
def fake_auth():
    return {
        "service": "test",
        "scopes": ["rules:read", "rules:write"],
        "roles": ["admin"],
    }


# Real Mongo (integration tests)
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

    yield


# Marker-aware FastAPI client
@pytest.fixture
def client(request, mongo_container, fake_mongo):
    is_integration = request.node.get_closest_marker("integration") is not None

    app.dependency_overrides[ruleset_write] = lambda: fake_auth()
    app.dependency_overrides[ruleset_read] = lambda: fake_auth()
    app.dependency_overrides[ruleset_admin] = lambda: fake_auth()

    if is_integration:
        request.getfixturevalue("integration_mongo_env")
    else:
        app.dependency_overrides[get_mongo] = lambda: fake_mongo

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

