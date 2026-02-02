import pytest
from tests.conftest import FakeMongo

pytestmark = pytest.mark.integration


def test_event_state_transition_persisted(run_once):
    mongo = FakeMongo(
        state={"event_id": "evt-1", "parsed": False},
        event={"_id": "evt-1", "raw": "hello"},
        cards=[{
            "name": "test-card",
            "selector": {"type": "raw", "value": "hello"},
        }],
    )

    run_once(mongo, extractor_json={"field": ["value"]})

    assert len(mongo.state_updates) == 1
    assert mongo.state_updates[0]["event_id"] == "evt-1"
    assert mongo.state_updates[0]["parsed"] is True
