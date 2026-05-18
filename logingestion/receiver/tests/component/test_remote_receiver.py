def test_remote_receiver_single_event_ok(remote_client, fake_writer):
    response = remote_client.post(
        "/logingestion/remote",
        json={
            "remote_from": {"source_addr": "1.1.1.1"},
            "data": "hello",
        },
    )

    assert response.status_code == 200
    assert len(fake_writer.items) == 1
    assert fake_writer.items[0]["source_addr"] == "1.1.1.1"
    assert fake_writer.items[0]["context_id"] == "default"


def test_remote_receiver_missing_data(remote_client):
    response = remote_client.post("/logingestion/remote", json={"remote_from": {"source_addr": "1.1.1.1"}})
    assert response.status_code == 400


def test_remote_receiver_bulk_ok(remote_client, fake_writer):
    response = remote_client.post(
        "/logingestion/remote/bulk",
        json={
            "events": [
                {"data": "one", "source_addr": "1.1.1.1", "kind": "udp"},
                {"data": "two", "source_addr": "2.2.2.2", "kind": "tcp"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.get_json()["accepted"] == 2
    assert len(fake_writer.items) == 2
