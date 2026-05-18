import os
import sys
import warnings
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from modules.auth.auth import get_identity

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

warnings.filterwarnings("ignore", category=DeprecationWarning)

from routers import logs  # noqa: E402


class FakeMongo:
    def __init__(self):
        self.data = {
            "events": [],
            "event_state": [],
            "parse_results": [],
            "detections": [],
            "incidents": [],
        }

    def _matches_value(self, actual, expected):
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$in":
                    if actual not in value:
                        return False
                elif op == "$gte":
                    if actual is None or actual < value:
                        return False
                elif op == "$lte":
                    if actual is None or actual > value:
                        return False
                elif op == "$gt":
                    if actual is None or actual <= value:
                        return False
                elif op == "$lt":
                    if actual is None or actual >= value:
                        return False
                else:
                    return False
            return True
        return actual == expected

    def _matches(self, item, filter_query):
        if not filter_query:
            return True
        for key, expected in filter_query.items():
            actual = item.get(key)
            if not self._matches_value(actual, expected):
                return False
        return True

    def _with_context(self, filter_query, context_id):
        query = dict(filter_query or {})
        # Unit tests often use tiny documents without context_id. Treat missing
        # context_id as acceptable so the fake stays lightweight, while still
        # filtering wrong explicit context_id values.
        if context_id is not None:
            query["__context_id"] = context_id
        return query

    def _matches_with_context(self, item, filter_query, context_id):
        if context_id is not None and item.get("context_id", context_id) != context_id:
            return False
        return self._matches(item, filter_query)

    def find(self, collection, filter_query):
        return [
            item
            for item in self.data.get(collection, [])
            if self._matches(item, filter_query)
        ]

    def find_one(self, collection, filter_query):
        items = self.find(collection, filter_query)
        return items[0] if items else None

    def find_sorted(self, collection, filter_query, sort, limit):
        items = self.find(collection, filter_query)
        for key, direction in reversed(sort or []):
            items = sorted(items, key=lambda item: item.get(key), reverse=direction < 0)
        return items[:limit]

    def find_with_context(self, collection, filter_query, context_id):
        return [
            item
            for item in self.data.get(collection, [])
            if self._matches_with_context(item, filter_query, context_id)
        ]

    def find_one_with_context(self, collection, filter_query, context_id):
        items = self.find_with_context(collection, filter_query, context_id)
        return items[0] if items else None

    def find_sorted_with_context(self, collection, filter_query, context_id, sort, limit):
        items = self.find_with_context(collection, filter_query, context_id)
        for key, direction in reversed(sort or []):
            items = sorted(items, key=lambda item: item.get(key), reverse=direction < 0)
        return items[:limit]


@pytest.fixture
def fake_mongo():
    return FakeMongo()


@pytest.fixture(autouse=True)
def override_mongo(fake_mongo):
    logs.get_mongo = lambda: fake_mongo


@pytest.fixture
def app():
    app = FastAPI()

    identity = {
        "type": "service",
        "service": "test",
        "service_id": "svc-test",
        "scopes": [
            "events:get",
            "dashboard:read",
        ],
        "context_id": "default",
    }

    # root auth dependency
    app.dependency_overrides[get_identity] = lambda: identity

    context = {
        "identity": identity,
        "context_id": identity["context_id"],
        "scopes": identity["scopes"],
    }

    dashboard_identity = {
        "type": "user",
        "user_id": "test",
        "email": "test@test.com",
        "scopes": ["dashboard:read"],
        "context_id": "default",
    }
    dashboard_context = {
        "identity": dashboard_identity,
        "context_id": dashboard_identity["context_id"],
        "scopes": dashboard_identity["scopes"],
    }

    # route-specific RBAC overrides
    app.dependency_overrides[logs.events_get_auth] = lambda: context
    app.dependency_overrides[logs.dashboard_auth] = lambda: dashboard_context

    app.include_router(logs.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)