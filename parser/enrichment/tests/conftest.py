import importlib
import pytest
import os

def _import_service_module():
    try:
        return importlib.import_module("app.enrichment")
    except Exception:
        return importlib.import_module("enrichment")

svc = _import_service_module()


class FakeMongo:
    # Minimal fake used by enrichment tests
    def __init__(self, state=None, event=None, cards=None):
        self._state = state
        self._event = event
        self._cards = cards or []
        self.parse_results = []
        self.state_updates = []

    def find_one(self, collection, query):
        if collection == "event_state":
            s, self._state = self._state, None
            return s
        if collection == "events":
            return self._event
        return None

    def find(self, collection, query):
        if collection == "parse_cards":
            return list(self._cards)
        return []

    def insert_parse_result(self, doc):
        self.parse_results.append(doc)
        return True

    def upsert_event_state(self, event_id, payload):
        self.state_updates.append({"event_id": event_id, **payload})
        return True


class StopLoop(Exception):
    # Raised to break daemon loop
    pass


@pytest.fixture()
def run_once(monkeypatch):
    # Runs exactly one daemon iteration
    def _runner(fake_mongo: FakeMongo, extractor_json=None, extractor_exc=None):
        # Bypass service token
        monkeypatch.setattr(
            svc,
            "service_auth_headers",
            lambda: {"Authorization": "Bearer test"},
        )

        # Force FakeMongo always
        monkeypatch.setattr(svc, "get_mongo", lambda: fake_mongo)

        # Stop loop after first sleep
        def _sleep(_):
            raise StopLoop()
        monkeypatch.setattr(svc.time, "sleep", _sleep)

        # Control extractor behavior
        if extractor_exc is not None:
            monkeypatch.setattr(
                svc,
                "call_extractor",
                lambda card, raw: (_ for _ in ()).throw(extractor_exc),
            )
        elif extractor_json is not None:
            monkeypatch.setattr(
                svc,
                "call_extractor",
                lambda card, raw: extractor_json,
            )

        # Ensure extractor env does not block
        monkeypatch.setenv("EXTRACTOR_SVC", "http://test/parse")
        try:
            monkeypatch.setattr(svc, "EXTRACTOR_SVC", "http://test/parse")
        except Exception:
            pass

        with pytest.raises(StopLoop):
            svc.main()

        return fake_mongo

    return _runner
