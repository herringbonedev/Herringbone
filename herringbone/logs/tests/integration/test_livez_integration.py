def test_livez_integration(client):
    r = client.get("/herringbone/logs/livez")
    assert r.status_code == 200
