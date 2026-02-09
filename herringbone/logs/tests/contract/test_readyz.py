def test_readyz_contract(client):
    r = client.get("/herringbone/logs/readyz")
    assert r.status_code == 200
    assert "ready" in r.json()
