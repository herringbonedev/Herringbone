from bson import ObjectId
from datetime import datetime, UTC


def test_dashboard_recent_events(client, fake_mongo):
    oid = ObjectId()
    fake_mongo.data["events"] = [
        {"_id": oid, "ingested_at": datetime.now(UTC), "source": "syslog"}
    ]
    fake_mongo.data["event_state"] = [
        {"event_id": oid, "detection": True, "severity": 10}
    ]

    r = client.get("/herringbone/logs/dashboard/recent-events")
    body = r.json()

    assert body[0]["event_id"] == str(oid)
    assert body[0]["detected"] is True
