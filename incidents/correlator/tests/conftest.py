import pytest
import warnings
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers import correlator


warnings.filterwarnings("ignore", category=DeprecationWarning)


class FakeMongo:
    def __init__(self, candidates=None, exc=None):
        self.candidates = candidates or []
        self.exc = exc

    def find_sorted(self, collection, filter_query, sort, limit):
        if self.exc:
            raise self.exc
        return self.candidates


@pytest.fixture
def fake_mongo():
    return FakeMongo()


@pytest.fixture
def fake_identity():
    return {
        "type": "service",
        "service": "test-correlator",
        "service_id": "svc-test",
        "scopes": ["incidents:correlate"],
        "context_id": "default",
    }


@pytest.fixture
def app(fake_mongo, fake_identity):
    app = FastAPI()
    app.include_router(correlator.router)

    app.dependency_overrides[correlator.get_mongo] = lambda: fake_mongo
    app.dependency_overrides[correlator.correlate_required] = lambda: fake_identity

    return app


@pytest.fixture
def client(app):
    return TestClient(app)