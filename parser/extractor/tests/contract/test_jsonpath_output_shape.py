from .conftest import client, PARSE_PATH


def test_jsonpath_output_is_object_map():
    response = client.post(
        PARSE_PATH,
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

