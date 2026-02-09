from bson import ObjectId
from datetime import datetime, UTC


def test_list_events_empty(client):
    r = client.get("/herringbone/logs/events")
    assert r.status_code == 200
    assert r.json() == []


def test_list_events_populated(client, fake_mongo):
    oid = ObjectId()
    fake_mongo.data["events"] = [
        {"_id": oid, "ingested_at": datetime.now(UTC), "source": "test"}
    ]

    r = client.get("/herringbone/logs/events")
    body = r.json()

    assert body[0]["_id"] == str(oid)
    assert "state" in body[0]
    assert "parsed" in body[0]
