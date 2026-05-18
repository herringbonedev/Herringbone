import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("flask")

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"

# Support both import styles used by the receiver code/tests:
#   import web
#   from app.batcher import ...
for path in (str(ROOT_DIR), str(APP_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from app import web, remote, forwarder
except Exception:
    import web  # type: ignore
    import remote  # type: ignore
    import forwarder  # type: ignore


class FakeMongo:
    def __init__(self):
        self.events = []
        self.states = []

    def insert_event(self, doc, context_id="default"):
        event_id = f"event-{len(self.events) + 1}"
        self.events.append({"event_id": event_id, "context_id": context_id, "doc": doc})
        return event_id

    def upsert_event_state(self, event_id, state, context_id="default"):
        self.states.append({"event_id": event_id, "context_id": context_id, "state": state})


class FakeWriter:
    def __init__(self):
        self.items = []
        self.drop = False

    def enqueue(self, data, source_addr, kind, context_id):
        if self.drop:
            return False
        self.items.append(
            {
                "data": data,
                "source_addr": source_addr,
                "kind": kind,
                "context_id": context_id,
            }
        )
        return True

    def stats(self):
        return {
            "queued_total": len(self.items),
            "dropped_total": 0,
            "queue_depth": 0,
        }


@pytest.fixture
def fake_mongo():
    return FakeMongo()


@pytest.fixture
def fake_writer():
    return FakeWriter()


@pytest.fixture(autouse=True)
def patch_receiver_dependencies(monkeypatch, fake_mongo, fake_writer):
    # Do not let tests open real Mongo connections.
    monkeypatch.setattr(web, "get_mongo", lambda: fake_mongo, raising=False)
    monkeypatch.setattr(remote, "get_mongo", lambda: fake_mongo, raising=False)

    # Do not let tests start the real background batch writer.
    monkeypatch.setattr(web, "get_writer", lambda: fake_writer, raising=False)
    monkeypatch.setattr(remote, "get_writer", lambda: fake_writer, raising=False)

    # Keep the ingestion-key model intact in production, but make tests local and deterministic.
    monkeypatch.setattr(web, "resolve_ingestion_key", lambda request, mongo: "default", raising=False)
    monkeypatch.setattr(remote, "resolve_ingestion_key", lambda request, mongo: "default", raising=False)

    # Keep HTTP receiver tests on local mode unless a test explicitly changes it.
    monkeypatch.setattr(web, "forward_route", None, raising=False)


@pytest.fixture
def web_client():
    web.app.config.update(TESTING=True)
    return web.app.test_client()


@pytest.fixture
def remote_client():
    remote.app.config.update(TESTING=True)
    return remote.app.test_client()


@pytest.fixture
def forwarder_module():
    return forwarder
