from .conftest import client, PARSE_PATH


def test_parse_response_has_results_field():
    response = client.post(
        PARSE_PATH,
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

