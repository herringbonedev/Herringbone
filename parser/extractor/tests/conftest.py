import os
import pytest
from testcontainers.mongodb import MongoDbContainer
from fastapi.testclient import TestClient
from app.main import app
from app.routers.extractor import extractor_call_scope


# Mongo container (integration only)
@pytest.fixture(scope="session")
def mongo_container():
    container = MongoDbContainer("mongo:7")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def integration_mongo_env(mongo_container):
    os.environ["MONGO_URI"] = mongo_container.get_connection_url()
    os.environ["MONGO_DB"] = "test_extractor"
    os.environ["AUTH_ENABLED"] = "false"
    yield


# Smart client fixture
@pytest.fixture
def client(request, mongo_container):
    is_integration = request.node.get_closest_marker("integration") is not None

    # Always bypass extractor auth
    app.dependency_overrides[extractor_call_scope] = lambda: {
        "scope": "extractor:call"
    }

    # Real Mongo only for integration tests
    if is_integration:
        request.getfixturevalue("integration_mongo_env")

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
