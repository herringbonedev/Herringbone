def valid_rule_payload():
    return {
        "name": "contract-rule",
        "severity": 10,
        "description": "contract test rule",
        "rule": {
            "key": "message",
            "regex": "ERROR",
        },
    }


def test_insert_rule_contract(client):
    res = client.post(
        "/detectionengine/ruleset/insert_rule",
        json=valid_rule_payload(),
    )

    # HTTP contract
    assert res.status_code == 200

    # Response contract
    body = res.json()
    assert isinstance(body, dict)
    assert body == {"inserted": True}
