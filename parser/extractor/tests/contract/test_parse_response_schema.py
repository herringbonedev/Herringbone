def test_parse_response_has_results_field(client):
    response = client.post(
        "/parser/extractor/parse",
        json={
            "card": {
                "selector": {"type": "test", "value": "test"},
            },
            "input": "example input",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert isinstance(body["results"], dict)

