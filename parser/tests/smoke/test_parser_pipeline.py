import pytest


@pytest.mark.smoke
def test_parser_pipeline_smoke(monkeypatch, integration_mongo_env):
    # Import enrichment entrypoints
    from enrichment.app import enrichment

    mongo = enrichment.get_mongo()

    # ---- Insert minimal event + state ----
    mongo.insert_one("events", {
        "_id": "evt-smoke",
        "raw": "hello world",
    })

    mongo.insert_one("event_state", {
        "event_id": "evt-smoke",
        "parsed": False,
    })

    # ---- Insert a minimal parse card ----
    mongo.insert_one("parse_cards", {
        "name": "smoke-card",
        "selector": {"type": "raw", "value": "hello"},
        "regex": [{"greeting": "hello"}],
    })

    # ---- Mock extractor (NO HTTP) ----
    monkeypatch.setattr(
        enrichment,
        "call_extractor",
        lambda card, raw: {"greeting": "hello"},
    )

    state = mongo.find_one("event_state", {"parsed": False})
    assert state is not None

    # ---- Run single-shot enrichment ----
    enrichment.process_event(mongo, state)

    # ---- Verify parse results ----
    result = mongo.find_one("parse_results", {"event_id": "evt-smoke"})
    assert result is not None
    assert result["results"] == {
        "greeting": ["hello"]
    }

    # ---- Verify state transition ----
    state = mongo.find_one("event_state", {"event_id": "evt-smoke"})
    assert state["parsed"] is True
