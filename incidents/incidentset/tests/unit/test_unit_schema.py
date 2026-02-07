import os
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from schema import IncidentSchema  # noqa: E402


def test_incident_schema_valid_and_invalid():
    v = IncidentSchema()

    ok = v({
        "title": "Something happened",
        "status": "open",
        "priority": "high",
        "notes": [{"author": "a", "timestamp": "t", "message": "m"}],
    })
    assert ok["valid"] is True
    assert ok["error"] is None

    bad = v({
        "title": "",
        "status": "nope",
        "priority": "low",
    })
    assert bad["valid"] is False
    assert isinstance(bad["error"], str)
