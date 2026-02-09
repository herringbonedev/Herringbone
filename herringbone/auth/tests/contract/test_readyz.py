def test_readyz(client):
    r = client.get("/herringbone/auth/readyz")
    assert r.status_code == 200
    assert "collections" in r.json()
