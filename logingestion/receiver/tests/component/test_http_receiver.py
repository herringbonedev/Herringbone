def test_http_receiver_ok(web_client):
    r = web_client.post("/logingestion/receiver", json={"msg": "hello"})
    assert r.status_code == 200


def test_http_receiver_no_body(web_client):
    r = web_client.post("/logingestion/receiver")
    assert r.status_code == 400
