def test_insert_rule_invalid_schema(client):
    res = client.post(
        "/detectionengine/ruleset/insert_rule",
        json={"name": "invalid"},
    )

    assert res.status_code == 400
    body = res.json()
    assert "detail" in body
