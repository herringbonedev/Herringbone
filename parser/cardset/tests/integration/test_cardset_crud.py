import pytest
pytestmark = pytest.mark.integration


def test_cardset_full_crud(client):
    # Insert
    insert = client.post(
        "/parser/cardset/insert_card",
        json={
            "name": "test",
            "selector": {"type": "host", "value": "example"},
            "regex": [{"pattern": "foo", "name": "bar"}],
        },
    )
    assert insert.status_code == 200
    assert insert.json()["ok"] is True

    # Pull ALL cards (authoritative read-after-write path)
    pull = client.get("/parser/cardset/pull_all_cards")
    assert pull.status_code == 200

    body = pull.json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert len(body["cards"]) == 1

    card = body["cards"][0]
    assert card["name"] == "test"
    assert card["selector"]["type"] == "host"
    assert card["selector"]["value"] == "example"
