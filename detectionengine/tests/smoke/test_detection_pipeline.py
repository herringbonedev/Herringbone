import pytest
import requests


@pytest.mark.smoke
def test_detector_pipeline_smoke(monkeypatch, integration_mongo_env):
    monkeypatch.setenv("MATCHER_API", "http://matcher.local/find_match")
    monkeypatch.setenv("ORCHESTRATOR_URL", "http://orchestrator.local")
    monkeypatch.setenv("DETECTIONS_COLLECTION_NAME", "detections")


    from processor import process_one
    from fetcher import _db
    import updater

    mongo = _db()

    mongo.insert_one("events", {
        "_id": "evt-smoke",
        "raw": "hello world",
    })

    mongo.insert_one("event_state", {
        "event_id": "evt-smoke",
        "parsed": True,
        "detected": False,
    })

    mongo.insert_one("rules", {
        "name": "smoke-rule",
        "severity": 50,
        "description": "smoke test rule",
        "rule": {"regex": "hello", "key": "raw"},
        "correlate_on": [],
    })

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "matched": True,
                "details": "ok",
            }

    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: FakeResponse(),
    )

    monkeypatch.setattr(
        updater,
        "notify_orchestrator",
        lambda payload: None,
    )

    result = process_one()
    assert result["status"] is True

    detection = mongo.find_one("detections", {"event_id": "evt-smoke"})
    assert detection is not None
    assert detection["detection"] is True
    assert detection["severity"] == 50

    state = mongo.find_one("event_state", {"event_id": "evt-smoke"})
    assert state["detected"] is True
