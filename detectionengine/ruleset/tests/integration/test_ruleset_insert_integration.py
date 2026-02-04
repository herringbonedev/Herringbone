import pytest


def valid_rule_payload():
    return {
        "name": "integration-rule",
        "severity": 20,
        "description": "integration test rule",
        "rule": {
            "key": "message",
            "regex": "ERROR",
        },
    }


@pytest.mark.integration
def test_insert_rule_integration(client):
    res = client.post(
        "/detectionengine/ruleset/insert_rule",
        json=valid_rule_payload(),
    )

    assert res.status_code == 200
    assert res.json() == {"inserted": True}
