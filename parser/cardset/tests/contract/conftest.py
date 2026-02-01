import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers.cardset import (
    get_mongo,
    cardset_write_user,
    cardset_admin_user,
    cardset_read_any,
)

# Fake mongo implementation
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


def fake_admin_user():
    return {"user": "admin", "roles": ["admin"]}


def fake_analyst_user():
    return {"user": "analyst", "roles": ["analyst"]}


def fake_service():
    return {"service": "test", "scopes": ["parser:cards:read"]}


@pytest.fixture(scope="session")
def client():
    # Dependency overrides
    app.dependency_overrides[get_mongo] = override_mongo
    app.dependency_overrides[cardset_write_user] = fake_analyst_user
    app.dependency_overrides[cardset_admin_user] = fake_admin_user
    app.dependency_overrides[cardset_read_any] = fake_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
