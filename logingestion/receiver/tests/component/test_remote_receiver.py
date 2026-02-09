def test_remote_receiver_ok(remote_client):
    payload = {
        "remote_from": {"source_addr": "1.1.1.1"},
        "data": "hello",
    }
    r = remote_client.post("/logingestion/remote", json=payload)
    assert r.status_code == 200


def test_remote_receiver_missing_source(remote_client):
    r = remote_client.post("/logingestion/remote", json={"data": "x"})
    assert r.status_code == 400
