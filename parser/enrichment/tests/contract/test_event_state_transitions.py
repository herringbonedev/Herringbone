from tests.conftest import FakeBulk, FakeMongo


def test_event_state_parsed_transitions_once_per_event(enrichment, monkeypatch):
    cards = [
        {"name": "c1", "selector": {"type": "raw", "value": "foo"}, "regex": []},
        {"name": "c2", "selector": {"type": "raw", "value": "foo"}, "regex": []},
    ]
    event = {"_id": "evt3", "context_id": "default", "raw": "abc foo def", "source": {"address": "9.9.9.9"}}
    states = [{"_id": "state3", "event_id": "evt3", "context_id": "default", "parsed": False}]
    mongo = FakeMongo(cards=cards)
    bulk = FakeBulk(events={"evt3": event})

    monkeypatch.setattr(
        enrichment,
        "call_extractor_batch_with_retry",
        lambda jobs, context_id: [
            {
                "event_id": job["event_id"],
                "card": enrichment.safe_card_label(job["card"]),
                "success": True,
                "results": {"k": "v"},
            }
            for job in jobs
        ],
    )

    enrichment.process_batch(mongo, bulk, "default", states)

    parsed_updates = [u for u in bulk.updates if u["set_fields"].get("parsed") is True]
    assert len(parsed_updates) == 1
    assert parsed_updates[0]["id_field"] == "_id"
    assert parsed_updates[0]["ids"] == ["state3"]


def test_event_not_found_marks_parsed_once(enrichment):
    states = [{"_id": "state_missing", "event_id": "evt_missing", "context_id": "default", "parsed": False}]
    mongo = FakeMongo(cards=[])
    bulk = FakeBulk(events={})

    enrichment.process_batch(mongo, bulk, "default", states)

    assert bulk.inserted == []
    parsed_updates = [u for u in bulk.updates if u["set_fields"].get("parsed") is True]
    assert len(parsed_updates) >= 1

    all_ids = [item for update in parsed_updates for item in update["ids"]]
    assert "evt_missing" in all_ids or "state_missing" in all_ids
