def test_register_then_login(client):
    payload = {"email": "user@example.com", "password": "password123"}

    r = client.post(
        "/herringbone/auth/register",
        json=payload,
        headers={"x-bootstrap-token": "test"},
    )
    assert r.status_code == 200

    r = client.post("/herringbone/auth/login", json=payload)
    assert r.status_code == 200
    assert "access_token" in r.json()
