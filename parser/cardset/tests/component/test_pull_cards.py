
def test_pull_cards_ok(client):
    r = client.post("/parser/cardset/pull_cards", json={
        "selector_type": "host",
        "selector_value": "example",
    })
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert "count" in body
