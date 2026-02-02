def test_parse_ok(client):
    r = client.post(
        "/parser/extractor/parse",
        json={
            "card": {
                "selector": {"type": "test", "value": "test"},
            },
            "input": "example",
        },
    )
    assert r.status_code == 200

