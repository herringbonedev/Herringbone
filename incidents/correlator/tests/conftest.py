import pytest
import warnings
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers import correlator


# Silence datetime.utcnow() deprecation in tests ONLY
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
def app(fake_mongo):
    app = FastAPI()
    app.include_router(correlator.router)

    # override mongo
    app.dependency_overrides[correlator.get_mongo] = lambda: fake_mongo

    # override auth ONLY
    app.dependency_overrides[correlator.correlate_required] = (
        lambda: {"scope": "incidents:correlate"}
    )

    return app


@pytest.fixture
def client(app):
    return TestClient(app)
