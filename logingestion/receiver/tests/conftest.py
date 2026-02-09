import os
import sys
import pytest

# Make app/ importable
APP_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "app")
)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import web
import remote
import inet

class FakeMongo:
    def __init__(self):
        self.events = []
        self.states = []

    def insert_event(self, doc):
        eid = f"event-{len(self.events)+1}"
        self.events.append((eid, doc))
        return eid

    def upsert_event_state(self, event_id, state):
        self.states.append((event_id, state))

@pytest.fixture
def fake_mongo():
    return FakeMongo()

@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch, fake_mongo):
    monkeypatch.setattr(inet, "get_mongo", lambda: fake_mongo)
    monkeypatch.setattr(web, "get_mongo", lambda: fake_mongo)
    monkeypatch.setattr(remote, "get_mongo", lambda: fake_mongo)

@pytest.fixture
def web_client():
    web.app.testing = True
    return web.app.test_client()

@pytest.fixture
def remote_client():
    remote.app.testing = True
    return remote.app.test_client()
