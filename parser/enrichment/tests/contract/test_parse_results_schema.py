from tests.conftest import FakeMongo


def _assert_common_fields(doc: dict):
    assert "event_id" in doc
    assert "card" in doc
    assert "created_at" in doc


def test_parse_results_document_schema_success(run_once):
    mongo = run_once(
        fake_mongo=FakeMongo(
            state={"event_id": "evt1", "parsed": False},
            event={"_id": "evt1", "raw": "foo", "source": {"address": "1.2.3.4"}},
            cards=[{"name": "c1", "selector": {"type": "raw", "value": "foo"}, "regex": []}],
        ),
        extractor_json={"field": ["value"]},
    )

    assert len(mongo.parse_results) == 1
    doc = mongo.parse_results[0]

    _assert_common_fields(doc)
    assert doc["event_id"] == "evt1"
    assert doc["card"] == "c1"
    assert "results" in doc
    assert isinstance(doc["results"], dict)

    # Contract: result values must be lists (enforced by service)
    for v in doc["results"].values():
        assert isinstance(v, list)

    # Contract: success docs must not have 'error'
    assert "error" not in doc


def test_parse_results_document_schema_error(run_once):
    mongo = run_once(
        fake_mongo=FakeMongo(
            state={"event_id": "evt2", "parsed": False},
            event={"_id": "evt2", "raw": "foo", "source": {"address": "1.2.3.4"}},
            cards=[{"name": "c1", "selector": {"type": "raw", "value": "foo"}, "regex": []}],
        ),
        extractor_exc=RuntimeError("boom"),
    )

    assert len(mongo.parse_results) == 1
    doc = mongo.parse_results[0]

    _assert_common_fields(doc)
    assert doc["event_id"] == "evt2"
    assert doc["card"] == "c1"
    assert "error" in doc
    assert isinstance(doc["error"], str)

    # Contract: error docs must not have 'results'
    assert "results" not in doc
