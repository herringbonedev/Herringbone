from bson import ObjectId


def test_get_event_not_found(client):
    oid = ObjectId()
    r = client.get(f"/herringbone/logs/events/{oid}")
    assert r.status_code == 404
