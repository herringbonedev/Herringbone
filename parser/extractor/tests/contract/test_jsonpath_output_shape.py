def test_jsonpath_output_is_object_map(client):
    response = client.post(
        "/parser/extractor/parse",
        json={
            "card": {
                "selector": {"type": "test", "value": "test"},
                "jsonp": [
                    {"path": "$.field"},
                ],
            },
            "input": {"field": "value"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["results"], dict)

