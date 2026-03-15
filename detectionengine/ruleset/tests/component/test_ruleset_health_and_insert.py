import pytest


def test_ruleset_livez(client):
    res = client.get("/detectionengine/ruleset/livez")

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ruleset_readyz(client):
    res = client.get("/detectionengine/ruleset/readyz")

    assert res.status_code == 200
    assert res.json() == {"ready": True}


def test_ruleset_insert(client):
    payload = {
        "name": "test_rule",
        "severity": 50,
        "description": "test rule description",
        "rule": {
            "key": "test_rule_key",
            "regex": "error"
        }
    }

    res = client.post(
        "/detectionengine/ruleset/insert_rule",
        json=payload,
    )

    assert res.status_code == 200

    body = res.json()
    assert body["inserted"] is True