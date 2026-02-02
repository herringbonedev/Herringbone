import importlib
import os
import sys
import pytest

# --- Ensure parser/ is on sys.path ---
HERE = os.path.dirname(__file__)
ENRICHMENT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PARSER_DIR = os.path.abspath(os.path.join(ENRICHMENT_DIR, ".."))

if PARSER_DIR not in sys.path:
    sys.path.insert(0, PARSER_DIR)

# --- Import enrichment service module ---
svc = importlib.import_module("enrichment.app.enrichment")


class FakeMongo:
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
        if collection in ("cards", "parse_cards"):
            return list(self._cards)
        return []

    def insert_parse_result(self, doc):
        self.parse_results.append(doc)
        return True

    def upsert_event_state(self, event_id, payload):
        self.state_updates.append({"event_id": event_id, **payload})
        return True


class StopLoop(Exception):
    pass


@pytest.fixture()
def run_once(monkeypatch):
    def _runner(fake_mongo, extractor_json=None, extractor_exc=None):
        monkeypatch.setattr(
            svc,
            "service_auth_headers",
            lambda: {"Authorization": "Bearer test"},
        )

        monkeypatch.setattr(svc, "get_mongo", lambda: fake_mongo)

        def _sleep(_):
            raise StopLoop()

        monkeypatch.setattr(svc.time, "sleep", _sleep)

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

        monkeypatch.setenv("EXTRACTOR_SVC", "http://test/parse")
        monkeypatch.setattr(svc, "EXTRACTOR_SVC", "http://test/parse", raising=False)

        with pytest.raises(StopLoop):
            svc.main()

        return fake_mongo

    return _runner
