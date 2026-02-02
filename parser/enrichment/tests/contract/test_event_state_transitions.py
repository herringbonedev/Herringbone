from tests.conftest import FakeMongo


def test_event_state_parsed_transitions_once_per_event(run_once):
    # Two matching cards should still produce exactly one parsed=True transition.
    mongo = run_once(
        fake_mongo=FakeMongo(
            state={"event_id": "evt3", "parsed": False},
            event={"_id": "evt3", "raw": "abc foo def", "source": {"address": "9.9.9.9"}},
            cards=[
                {"name": "c1", "selector": {"type": "raw", "value": "foo"}, "regex": []},
                {"name": "c2", "selector": {"type": "raw", "value": "foo"}, "regex": []},
            ],
        ),
        extractor_json={"k": ["v"]},
    )

    # Contract: parsed state transition occurs exactly once.
    parsed_updates = [u for u in mongo.state_updates if u.get("parsed") is True]
    assert len(parsed_updates) == 1
    assert parsed_updates[0]["event_id"] == "evt3"


def test_event_not_found_marks_parsed_once(run_once):
    mongo = run_once(
        fake_mongo=FakeMongo(
            state={"event_id": "evt_missing", "parsed": False},
            event=None,
            cards=[],
        ),
        extractor_json={"k": ["v"]},
    )

    parsed_updates = [u for u in mongo.state_updates if u.get("parsed") is True]
    assert len(parsed_updates) == 1
    assert parsed_updates[0]["event_id"] == "evt_missing"

    # Contract: no parse_results are inserted if event doesn't exist.
    assert mongo.parse_results == []
