def test_livez(client):
    res = client.get("/parser/cardset/livez")
    assert res.status_code == 200
    assert res.json()["ok"] is True

def test_readyz(client):
    res = client.get("/parser/cardset/readyz")
    assert res.status_code in (200, 503)
