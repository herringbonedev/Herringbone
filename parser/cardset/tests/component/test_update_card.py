
def test_update_card_ok(client):
    r = client.post("/parser/cardset/update_card", json={
        "name": "test",
        "selector": {"type": "host", "value": "example"},
        "regex": [{"pattern": "foo", "name": "bar"}],
    })
    assert r.status_code == 200
    assert "ok" in r.json()
