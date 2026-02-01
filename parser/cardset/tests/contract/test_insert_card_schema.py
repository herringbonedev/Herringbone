def test_insert_card_response_shape(client):
    response = client.post(
        "/parser/cardset/insert_card",
        json={
            "name": "test",
            "selector": {"type": "host", "value": "example"},
            "regex": [{"pattern": "foo", "name": "bar"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "ok" in body
    assert "message" in body
