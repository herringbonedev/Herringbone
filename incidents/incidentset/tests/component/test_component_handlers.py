import anyio
from fastapi import HTTPException
from bson import ObjectId

from routers import incidentset


def test_insert_incident_invalid_payload_400(fake_mongo):
    async def run():
        # Missing required fields title/priority; status gets default but schema requires title/priority.
        payload = incidentset.IncidentCreate.model_validate({"status": "open"})
        await incidentset.insert_incident(payload=payload, mongo=fake_mongo, auth={"scope": "test"})

    try:
        anyio.run(run)
        assert False, "Expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 500


def test_insert_incident_valid_inserts(fake_mongo):
    async def run():
        payload = incidentset.IncidentCreate.model_validate({
            "title": "T",
            "priority": "low",
            "status": "open",
        })
        return await incidentset.insert_incident(payload=payload, mongo=fake_mongo, auth={"scope": "test"})

    resp = anyio.run(run)
    assert resp == {"inserted": True}
    assert len(fake_mongo.inserted) == 1
    inserted_doc = fake_mongo.inserted[0]["doc"]
    assert inserted_doc["title"] == "T"
    assert inserted_doc["priority"] == "low"
    assert inserted_doc["status"] == "open"
    assert "created_at" in inserted_doc
    assert "last_updated" in inserted_doc
    assert "state" in inserted_doc and "last_updated" in inserted_doc["state"]


def test_update_incident_missing_id_400(fake_mongo):
    async def run():
        await incidentset.update_incident(payload={}, mongo=fake_mongo, auth={"scope": "test"})

    try:
        anyio.run(run)
        assert False, "Expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 400
        assert e.detail == "Missing _id"


def test_update_incident_builds_set_and_push(fake_mongo):
    oid = ObjectId()

    async def run():
        payload = {
            "_id": str(oid),
            "title": "New title",
            "events": ["e1", "e2"],
            "notes": [{"author": "a", "timestamp": "t", "message": "m"}],
        }
        return await incidentset.update_incident(payload=payload, mongo=fake_mongo, auth={"scope": "test"})

    resp = anyio.run(run)
    assert resp == {"updated": True}

    # Ensure connection lifecycle happened
    assert fake_mongo.opened is True
    assert fake_mongo.closed is True

    # Validate update doc structure
    col = fake_mongo._db[incidentset.incidents_collection()]
    upd = col.last_update_one["update"]
    assert "$set" in upd
    assert "$push" in upd
    assert upd["$set"]["title"] == "New title"
    assert "last_updated" in upd["$set"]
    assert "state.last_updated" in upd["$set"]
    assert upd["$push"]["events"]["$each"] == ["e1", "e2"]
    assert upd["$push"]["notes"]["$each"] == [{"author": "a", "timestamp": "t", "message": "m"}]
