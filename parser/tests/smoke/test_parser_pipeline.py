import pytest
from fastapi.testclient import TestClient


@pytest.mark.smoke
def test_parser_pipeline_smoke(integration_mongo_env):
    # ---- Cardset ----
    from cardset.app.main import app as cardset_app
    cardset = TestClient(cardset_app)

    r = cardset.post(
        "/parser/cardset/insert_card",
        json={
            "name": "smoke-card",
            "selector": {"type": "raw", "value": "hello"},
            "regex": [{"pattern": "hello", "name": "greeting"}],
        },
    )
    assert r.status_code == 200, r.text

    # ---- Enrichment (single-shot execution) ----
    from enrichment.app.enrichment import get_mongo, process_event

    mongo = get_mongo()

    mongo.insert_one("events", {
        "_id": "evt-smoke",
        "raw": "hello world",
    })

    mongo.insert_one("event_state", {
        "event_id": "evt-smoke",
        "parsed": False,
    })

    state = mongo.find_one("event_state", {"parsed": False})
    assert state is not None

    process_event(mongo, state)

    # ---- Verify parse results ----
    result = mongo.find_one("parse_results", {"event_id": "evt-smoke"})
    assert result is not None
    assert "results" in result
    assert "greeting" in result["results"]
    assert result["results"]["greeting"] == ["hello"]
