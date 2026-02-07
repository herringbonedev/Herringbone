def test_search_endpoint(client):
    r = client.post("/search", json={})
    assert r.status_code in (200, 400, 404)
