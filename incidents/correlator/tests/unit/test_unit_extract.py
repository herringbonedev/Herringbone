from app.routers import correlator


def test_extract_correlate_values_basic():
    event = {
        "src": {"ip": "1.2.3.4"},
        "tags": ["b", "a", "a"],
    }

    identity, filters = correlator.extract_correlate_values(
        event,
        ["src.ip", "tags", "missing.path"],
    )

    assert identity == {
        "src": {"ip": "1.2.3.4"},
        "tags": ["b", "a", "a"],
    }

    assert {"correlation_identity.src.ip": "1.2.3.4"} in filters
    assert {"correlation_identity.tags": {"$all": ["a", "b"]}} in filters
