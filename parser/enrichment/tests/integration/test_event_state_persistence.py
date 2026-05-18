from tests.conftest import FakeBulk, FakeMongo


def test_event_state_transition_persisted(enrichment, monkeypatch):
    cards = [{"name": "test-card", "selector": {"type": "raw", "value": "hello"}, "regex": []}]
    event = {"_id": "evt-1", "context_id": "default", "raw": "hello", "source": {"address": "1.2.3.4"}}
    states = [{"_id": "state-1", "event_id": "evt-1", "context_id": "default", "parsed": False}]
    mongo = FakeMongo(cards=cards)
    bulk = FakeBulk(events={"evt-1": event})

    monkeypatch.setattr(
        enrichment,
        "call_extractor_batch_with_retry",
        lambda jobs, context_id: [
            {
                "event_id": "evt-1",
                "card": "test-card",
                "success": True,
                "results": {"field": "value"},
            }
        ],
    )

    enrichment.process_batch(mongo, bulk, "default", states)

    parsed_updates = [u for u in bulk.updates if u["set_fields"].get("parsed") is True]
    assert len(parsed_updates) == 1
    assert parsed_updates[0]["id_field"] == "_id"
    assert parsed_updates[0]["ids"] == ["state-1"]
