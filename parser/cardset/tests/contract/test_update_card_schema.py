def test_update_card_response_shape(client):
    response = client.post(
        "/parser/cardset/update_card",
        json={
            "name": "test",
            "selector": {"type": "host", "value": "example"},
            "regex": [{"pattern": "foo", "name": "bar"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "matched" in body
    assert "modified" in body
    assert "upserted_id" in body
