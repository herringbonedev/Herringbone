def test_healthz(client):
    r = client.get("/herringbone/auth/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
