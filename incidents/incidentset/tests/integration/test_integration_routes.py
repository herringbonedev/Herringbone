from bson import ObjectId


def test_get_incidents_returns_list(client, fake_mongo):
    fake_mongo.docs = [{"_id": ObjectId(), "title": "t", "status": "open", "priority": "low"}]

    r = client.get("/incidents/incidentset/get_incidents")
    assert r.status_code == 200

    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["title"] == "t"


def test_get_incident_404_when_missing(client, fake_mongo):
    fake_mongo.one = None
    r = client.get(f"/incidents/incidentset/get_incident/{ObjectId()}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Incident not found"


def test_get_incident_200_when_found(client, fake_mongo):
    oid = ObjectId()
    fake_mongo.one = {"_id": oid, "title": "t", "status": "open", "priority": "low"}

    r = client.get(f"/incidents/incidentset/get_incident/{oid}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "t"


def test_insert_incident_200(client, fake_mongo):
    r = client.post(
        "/incidents/incidentset/insert_incident",
        json={"title": "t", "status": "open", "priority": "medium"},
    )
    assert r.status_code == 200
    assert r.json() == {"inserted": True}
    assert len(fake_mongo.inserted) == 1


def test_update_incident_200(client, fake_mongo):
    oid = ObjectId()
    r = client.post(
        "/incidents/incidentset/update_incident",
        json={"_id": str(oid), "title": "new", "events": ["e1"]},
    )
    assert r.status_code == 200
    assert r.json() == {"updated": True}
