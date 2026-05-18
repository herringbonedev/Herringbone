from tests.conftest import FakeBulk, FakeMongo


def test_process_batch_writes_parse_result_and_marks_by_state_id(enrichment, monkeypatch):
    cards = [{"name": "ssh-card", "selector": {"type": "raw", "value": "Failed password"}, "regex": []}]
    event = {"_id": "evt-1", "context_id": "default", "raw": "Failed password for epstest", "source": {"address": "1.2.3.4"}}
    states = [{"_id": "state-1", "event_id": "evt-1", "context_id": "default", "parsed": False}]

    mongo = FakeMongo(cards=cards)
    bulk = FakeBulk(events={"evt-1": event})

    monkeypatch.setattr(
        enrichment,
        "call_extractor_batch_with_retry",
        lambda jobs, context_id: [
            {
                "event_id": jobs[0]["event_id"],
                "card": enrichment.safe_card_label(jobs[0]["card"]),
                "success": True,
                "results": {"auth_result": "Failed"},
            }
        ],
    )

    enrichment.process_batch(mongo, bulk, "default", states)

    assert len(bulk.inserted) == 1
    assert bulk.inserted[0]["event_id"] == "evt-1"
    assert bulk.inserted[0]["card"] == "ssh-card"
    assert bulk.inserted[0]["results"] == {"auth_result": ["Failed"]}

    parsed_updates = [u for u in bulk.updates if u["set_fields"].get("parsed") is True]
    assert len(parsed_updates) == 1
    assert parsed_updates[0]["id_field"] == "_id"
    assert parsed_updates[0]["ids"] == ["state-1"]


def test_process_batch_regex_path_does_not_call_extractor(enrichment, monkeypatch):
    cards = [
        {
            "name": "regex-card",
            "selector": {"type": "raw", "value": "Accepted password"},
            "regex": [{"name": "auth_result", "pattern": "Accepted password"}],
        }
    ]
    event = {"_id": "evt-2", "context_id": "default", "raw": "Accepted password for root", "source": {"address": "1.2.3.4"}}
    states = [{"_id": "state-2", "event_id": "evt-2", "context_id": "default", "parsed": False}]

    mongo = FakeMongo(cards=cards)
    bulk = FakeBulk(events={"evt-2": event})

    def should_not_run(*args, **kwargs):
        raise AssertionError("extractor should not be called when regex succeeds")

    monkeypatch.setattr(enrichment, "call_extractor_batch_with_retry", should_not_run)
    enrichment.process_batch(mongo, bulk, "default", states)

    assert len(bulk.inserted) == 1
    assert bulk.inserted[0]["event_id"] == "evt-2"
    assert "auth_result" in bulk.inserted[0]["results"]


def test_missing_event_marks_parsed_without_parse_result(enrichment):
    states = [{"_id": "state-3", "event_id": "missing-event", "context_id": "default", "parsed": False}]
    mongo = FakeMongo(cards=[])
    bulk = FakeBulk(events={})

    enrichment.process_batch(mongo, bulk, "default", states)

    assert bulk.inserted == []
    parsed_updates = [u for u in bulk.updates if u["set_fields"].get("parsed") is True]
    assert len(parsed_updates) >= 1

    all_ids = [item for update in parsed_updates for item in update["ids"]]
    assert "missing-event" in all_ids or "state-3" in all_ids
