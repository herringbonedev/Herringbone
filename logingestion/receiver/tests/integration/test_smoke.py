def test_smoke(web_client):
    r = web_client.get("/does-not-exist")
    assert r.status_code in (404, 405)
