def test_auth_smoke(client):
    r = client.get("/herringbone/auth/healthz")
    assert r.status_code == 200
