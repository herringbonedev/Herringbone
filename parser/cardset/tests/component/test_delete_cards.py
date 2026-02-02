
def test_delete_cards_ok(client):
    r = client.post("/parser/cardset/delete_cards", json={
        "selector_type": "host",
        "selector_value": "example",
    })
    assert r.status_code == 200
    assert "deleted" in r.json()
