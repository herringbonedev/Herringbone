
def test_livez(client):
    assert client.get("/parser/cardset/livez").status_code == 200

def test_readyz(client):
    r = client.get("/parser/cardset/readyz")
    assert r.status_code in (200, 503)
