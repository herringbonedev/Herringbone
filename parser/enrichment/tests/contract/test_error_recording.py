import importlib
import pytest

from tests.contract.conftest import FakeMongo, StopLoop


def _import_service_module():
    try:
        return importlib.import_module("app.enrichment")
    except Exception:
        return importlib.import_module("enrichment")


svc = _import_service_module()


def test_failures_recorded_no_silent_data_loss(monkeypatch):
    mongo = FakeMongo(
        state={"event_id": "evt4", "parsed": False},
        event={"_id": "evt4", "raw": "foo bar", "source": {"address": "1.1.1.1"}},
        cards=[
            {"name": "ok_card", "selector": {"type": "raw", "value": "foo"}, "regex": []},
            {"name": "bad_card", "selector": {"type": "raw", "value": "foo"}, "regex": []},
        ],
    )

    monkeypatch.setattr(svc, "service_auth_headers", lambda: {"Authorization": "Bearer test"})
    monkeypatch.setattr(svc, "get_mongo", lambda: mongo)
    monkeypatch.setenv("EXTRACTOR_SVC", "http://test/parse")
    try:
        monkeypatch.setattr(svc, "EXTRACTOR_SVC", "http://test/parse")
    except Exception:
        pass

    def _sleep(_):
        raise StopLoop()
    monkeypatch.setattr(svc.time, "sleep", _sleep)

    def _call_extractor(card, raw):
        if card.get("name") == "bad_card":
            raise RuntimeError("extractor failed")
        return {"field": ["value"]}

    monkeypatch.setattr(svc, "call_extractor", _call_extractor)

    with pytest.raises(StopLoop):
        svc.main()

    assert len(mongo.parse_results) == 2

    ok_docs = [d for d in mongo.parse_results if d.get("card") == "ok_card"]
    bad_docs = [d for d in mongo.parse_results if d.get("card") == "bad_card"]

    assert len(ok_docs) == 1
    assert "results" in ok_docs[0]
    assert "error" not in ok_docs[0]

    assert len(bad_docs) == 1
    assert "error" in bad_docs[0]
    assert "results" not in bad_docs[0]
