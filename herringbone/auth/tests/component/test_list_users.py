def test_list_users(client):
    r = client.get("/herringbone/auth/users")
    assert r.status_code == 200
    assert "users" in r.json()
