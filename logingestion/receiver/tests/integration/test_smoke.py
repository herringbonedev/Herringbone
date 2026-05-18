def test_smoke_unknown_route(web_client):
    response = web_client.get("/does-not-exist")
    assert response.status_code in (404, 405)


def test_health_route(web_client):
    response = web_client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
