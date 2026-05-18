def test_http_receiver_single_event_ok(web_client, fake_writer):
    response = web_client.post("/logingestion/receiver", json={"msg": "hello"})

    assert response.status_code == 200
    assert len(fake_writer.items) == 1
    assert fake_writer.items[0]["context_id"] == "default"
    assert fake_writer.items[0]["kind"] == "http"


def test_http_receiver_no_body(web_client):
    response = web_client.post("/logingestion/receiver")
    assert response.status_code == 400


def test_http_receiver_bulk_ok(web_client, fake_writer):
    response = web_client.post(
        "/logingestion/receiver/bulk",
        json={
            "events": [
                {"data": "one", "source_addr": "1.1.1.1"},
                {"raw": "two", "source_addr": "2.2.2.2"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.get_json()["accepted"] == 2
    assert len(fake_writer.items) == 2
