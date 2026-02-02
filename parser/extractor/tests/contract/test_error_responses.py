def test_jsonpath_error_is_string_field(client):
    response = client.post(
        "/parser/extractor/parse",
        json={
            "card": {
                "selector": {"type": "test", "value": "test"},
                "jsonp": [{"path": "$.missing"}],
            },
            "input": "not valid json",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert "results" in body
    assert "jsonp_error" in body["results"]
    assert isinstance(body["results"]["jsonp_error"], str)

