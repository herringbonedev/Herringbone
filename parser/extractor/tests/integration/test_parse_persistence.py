def test_parse_persists_results(client):
    r = client.post(
        "/parser/extractor/parse",
        json={
            "card": {
                "selector": {"type": "host", "value": "example"},
                "regex": [{"pattern": "foo", "name": "match"}],
            },
            "input": "foo bar",
        },
    )

    assert r.status_code == 200
    body = r.json()

    assert "results" in body
    assert "match" in body["results"]  # key exists
    assert body["results"]["match"] == ["foo"]  # regex outputs are lists
