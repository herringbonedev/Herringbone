from tests.conftest import FakeBulk, FakeMongo, StopLoop


def test_stoploop_compatibility_import():
    assert issubclass(StopLoop, Exception)


def test_failures_recorded_no_silent_data_loss(enrichment, monkeypatch):
    cards = [
        {"name": "ok_card", "selector": {"type": "raw", "value": "foo"}, "regex": []},
        {"name": "bad_card", "selector": {"type": "raw", "value": "foo"}, "regex": []},
    ]
    event = {"_id": "evt4", "context_id": "default", "raw": "foo bar", "source": {"address": "1.1.1.1"}}
    states = [{"_id": "state4", "event_id": "evt4", "context_id": "default", "parsed": False}]
    mongo = FakeMongo(cards=cards)
    bulk = FakeBulk(events={"evt4": event})

    def _extractor(jobs, context_id):
        results = []
        for job in jobs:
            card = enrichment.safe_card_label(job["card"])
            if card == "bad_card":
                results.append({
                    "event_id": job["event_id"],
                    "card": card,
                    "success": False,
                    "error": "extractor failed",
                })
            else:
                results.append({
                    "event_id": job["event_id"],
                    "card": card,
                    "success": True,
                    "results": {"field": "value"},
                })
        return results

    monkeypatch.setattr(enrichment, "call_extractor_batch_with_retry", _extractor)
    enrichment.process_batch(mongo, bulk, "default", states)

    assert len(bulk.inserted) == 2

    ok_docs = [d for d in bulk.inserted if d.get("card") == "ok_card"]
    bad_docs = [d for d in bulk.inserted if d.get("card") == "bad_card"]

    assert len(ok_docs) == 1
    assert "results" in ok_docs[0]
    assert "error" not in ok_docs[0]

    assert len(bad_docs) == 1
    assert "error" in bad_docs[0]
    assert "results" not in bad_docs[0]
