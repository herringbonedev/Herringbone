from app.main import app


def valid_rule_payload():
    return {
        "name": "unauthorized-rule",
        "severity": 5,
        "description": "should fail auth",
        "rule": {
            "key": "message",
            "regex": "ERROR",
        },
    }


def test_insert_rule_requires_auth(client):
    # Remove all dependency overrides (auth + mongo)
    app.dependency_overrides.clear()

    res = client.post(
        "/detectionengine/ruleset/insert_rule",
        json=valid_rule_payload(),
    )

    # 401 or 403 is acceptable depending on auth implementation
    assert res.status_code in (401, 403)
