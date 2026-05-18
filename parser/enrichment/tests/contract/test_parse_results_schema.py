from tests.conftest import FakeBulk, FakeMongo


def test_parse_results_document_schema_success(enrichment, monkeypatch):
    cards = [{"name": "c1", "selector": {"type": "raw", "value": "foo"}, "regex": []}]
    event = {"_id": "evt1", "context_id": "default", "raw": "foo", "source": {"address": "1.2.3.4"}}
    states = [{"_id": "state1", "event_id": "evt1", "context_id": "default", "parsed": False}]
    mongo = FakeMongo(cards=cards)
    bulk = FakeBulk(events={"evt1": event})

    monkeypatch.setattr(
        enrichment,
        "call_extractor_batch_with_retry",
        lambda jobs, context_id: [
            {
                "event_id": "evt1",
                "card": "c1",
                "success": True,
                "results": {"field": "value"},
            }
        ],
    )

    enrichment.process_batch(mongo, bulk, "default", states)

    assert len(bulk.inserted) == 1
    doc = bulk.inserted[0]
    assert doc["event_id"] == "evt1"
    assert doc["card"] == "c1"
    assert "created_at" in doc
    assert doc["results"] == {"field": ["value"]}
    assert "error" not in doc


def test_parse_results_document_schema_error(enrichment, monkeypatch):
    cards = [{"name": "c1", "selector": {"type": "raw", "value": "foo"}, "regex": []}]
    event = {"_id": "evt2", "context_id": "default", "raw": "foo", "source": {"address": "1.2.3.4"}}
    states = [{"_id": "state2", "event_id": "evt2", "context_id": "default", "parsed": False}]
    mongo = FakeMongo(cards=cards)
    bulk = FakeBulk(events={"evt2": event})

    monkeypatch.setattr(
        enrichment,
        "call_extractor_batch_with_retry",
        lambda jobs, context_id: [
            {
                "event_id": "evt2",
                "card": "c1",
                "success": False,
                "error": "boom",
            }
        ],
    )

    enrichment.process_batch(mongo, bulk, "default", states)

    assert len(bulk.inserted) == 1
    doc = bulk.inserted[0]
    assert doc["event_id"] == "evt2"
    assert doc["card"] == "c1"
    assert "error" in doc
    assert "results" not in doc
