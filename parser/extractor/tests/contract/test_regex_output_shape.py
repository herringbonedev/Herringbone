def test_regex_output_is_object_map(client):
    response = client.post(
        "/parser/extractor/parse",
        json={
            "card": {
                "selector": {"type": "test", "value": "test"},
                "regex": [
                    {"pattern": "foo", "name": "match"},
                ],
            },
            "input": "foo bar",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["results"], dict)

