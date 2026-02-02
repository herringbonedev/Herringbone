import os
import pytest
from fastapi.testclient import TestClient
from testcontainers.mongodb import MongoDbContainer
from urllib.parse import urlparse
from pymongo import MongoClient
from pymongo.errors import OperationFailure

from app.main import app
from app.routers.cardset import (
    get_mongo,
    cardset_write_user,
    cardset_admin_user,
    cardset_read_any,
)

# Fake mongo for non-integration tests
class FakeMongo:
    def find_one(self, *args, **kwargs):
        return None

    def find(self, *args, **kwargs):
        return []

    def insert_one(self, *args, **kwargs):
        return True

    def upsert_one(self, *args, **kwargs):
        return "fake_id"


def override_mongo():
    return FakeMongo()


# Fake auth dependencies
def fake_admin_user():
    return {"user": "admin", "roles": ["admin"]}


def fake_analyst_user():
    return {"user": "analyst", "roles": ["analyst"]}


def fake_service():
    return {"service": "test", "scopes": ["parser:cards:read"]}


# Real Mongo container for integration tests
@pytest.fixture(scope="session")
def mongo_container():
    container = MongoDbContainer("mongo:7")
    container.start()
    yield container
    container.stop()


# Wire Mongo env for integration without double-auth and with correct authSource behavior
@pytest.fixture(scope="session")
def integration_mongo_env(mongo_container):
    url = mongo_container.get_connection_url()
    parsed = urlparse(url)

    host = f"{parsed.hostname}:{parsed.port}"
    db_name = "herringbone"
    hb_user = "herringbone_test"
    hb_pass = "herringbone_test"

    # If container uses auth, create a db-scoped user so authSource defaults correctly
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


# Marker-aware client fixture
@pytest.fixture
def client(request, mongo_container):
    is_integration = request.node.get_closest_marker("integration") is not None

    app.dependency_overrides[cardset_write_user] = fake_analyst_user
    app.dependency_overrides[cardset_admin_user] = fake_admin_user
    app.dependency_overrides[cardset_read_any] = fake_service

    if is_integration:
        request.getfixturevalue("integration_mongo_env")
    else:
        app.dependency_overrides[get_mongo] = override_mongo

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
