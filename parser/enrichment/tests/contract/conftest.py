import importlib
import pytest


def _import_service_module():
    """
    Supports either:
      - parser/enrichment/app/enrichment.py   -> import as app.enrichment
      - enrichment.py in CWD                 -> import as enrichment
    """
    try:
        return importlib.import_module("app.enrichment")
    except Exception:
        return importlib.import_module("enrichment")


svc = _import_service_module()


class FakeMongo:
    """
    Minimal fake for the methods used by enrichment service.
    Captures inserts + state updates for assertions.
    """
    def __init__(self, state=None, event=None, cards=None):
        self._state = state
        self._event = event
        self._cards = cards or []
        self.parse_results = []
        self.state_updates = []

    def find_one(self, collection, query):
        if collection == "event_state":
            # Only return once, then behave like empty queue
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
    """Raised by patched sleep() to break the daemon loop."""
    pass


@pytest.fixture()
def run_once(monkeypatch):
    """
    Run one poll iteration of the daemon:
    - patches get_mongo() to return the provided FakeMongo
    - patches time.sleep() to stop the loop after the first iteration
    - patches service_auth_headers() to avoid reading docker secret
    - patches call_extractor() for deterministic results
    """
    def _runner(fake_mongo: FakeMongo, extractor_json=None, extractor_exc: Exception | None = None):
        # Avoid reading /run/secrets/service_token
        monkeypatch.setattr(svc, "service_auth_headers", lambda: {"Authorization": "Bearer test"})

        # Force get_mongo() to return our fake
        monkeypatch.setattr(svc, "get_mongo", lambda: fake_mongo)

        # Break after first loop iteration (after it calls sleep)
        def _sleep(_):
            raise StopLoop()
        monkeypatch.setattr(svc.time, "sleep", _sleep)

        # Patch extractor call path
        if extractor_exc is not None:
            monkeypatch.setattr(svc, "call_extractor", lambda card, raw: (_ for _ in ()).throw(extractor_exc))
        elif extractor_json is not None:
            monkeypatch.setattr(svc, "call_extractor", lambda card, raw: extractor_json)

        # Ensure EXTRACTOR_SVC check doesn't bite tests
        monkeypatch.setenv("EXTRACTOR_SVC", "http://test/parse")
        try:
            monkeypatch.setattr(svc, "EXTRACTOR_SVC", "http://test/parse")
        except Exception:
            pass

        with pytest.raises(StopLoop):
            svc.main()

        return fake_mongo

    return _runner
