from .conftest import client, PARSE_PATH


def test_regex_output_is_object_map():
    response = client.post(
        PARSE_PATH,
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

