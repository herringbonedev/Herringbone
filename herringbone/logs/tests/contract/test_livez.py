def test_livez_contract(client):
    r = client.get("/herringbone/logs/livez")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
