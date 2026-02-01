def test_delete_card_response_shape(client):
    response = client.post(
        "/parser/cardset/delete_cards",
        json={
            "selector_type": "host",
            "selector_value": "example",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert isinstance(body["deleted"], int)
