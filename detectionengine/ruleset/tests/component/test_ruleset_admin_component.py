def test_delete_rule_invalid_objectid(client):
    res = client.get(
        "/detectionengine/ruleset/delete_rule?id=not-an-objectid"
    )

    assert res.status_code == 400
