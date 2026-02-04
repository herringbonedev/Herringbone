def valid_rule_payload(name="test-rule", regex="ERROR"):
    return {
        "name": name,
        "severity": 50,
        "description": "simple test rule",
        "rule": {
            "key": "message",
            "regex": regex,
        },
    }


def test_ruleset_livez(client):
    res = client.get("/detectionengine/ruleset/livez")
    assert res.status_code == 200
    assert res.json() == "OK"


def test_insert_rule_success(client):
    res = client.post(
        "/detectionengine/ruleset/insert_rule",
        json=valid_rule_payload(),
    )

    assert res.status_code == 200
    assert res.json() == {"inserted": True}


def test_get_rules_returns_list(client):
    client.post(
        "/detectionengine/ruleset/insert_rule",
        json=valid_rule_payload(name="rule1", regex="WARN"),
    )

    res = client.get("/detectionengine/ruleset/get_rules")

    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["name"] == "rule1"
