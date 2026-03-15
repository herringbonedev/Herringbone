import anyio
from fastapi import HTTPException
from starlette.requests import Request
from bson import ObjectId

from routers import incidentset


def fake_request():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/incidents/incidentset",
        "headers": [],
        "client": ("testclient", 1234),
    }
    return Request(scope)


fake_identity = {
    "type": "user",
    "id": "test-user",
    "email": "test@example.com",
    "scopes": ["incidents:read", "incidents:write"],
    "context_id": "default",
}


def test_insert_incident_invalid_payload_400(fake_mongo):

    async def run():
        payload = incidentset.IncidentCreate.model_validate({"status": "open"})

        await incidentset.insert_incident(
            payload=payload,
            request=fake_request(),
            mongo=fake_mongo,
            identity=fake_identity,
        )

    try:
        anyio.run(run)
    except HTTPException as e:
        assert e.status_code == 400
    else:
        assert False, "Expected HTTPException"


def test_insert_incident_valid_inserts(fake_mongo):

    async def run():

        payload = incidentset.IncidentCreate.model_validate(
            {
                "title": "T",
                "priority": "low",
                "status": "open",
            }
        )

        return await incidentset.insert_incident(
            payload=payload,
            request=fake_request(),
            mongo=fake_mongo,
            identity=fake_identity,
        )

    resp = anyio.run(run)

    assert resp == {"inserted": True}
    assert len(fake_mongo.inserted) == 1


def test_update_incident_missing_id_400(fake_mongo):

    async def run():

        await incidentset.update_incident(
            payload={},
            request=fake_request(),
            mongo=fake_mongo,
            identity=fake_identity,
        )

    try:
        anyio.run(run)
    except HTTPException as e:
        assert e.status_code == 400
    else:
        assert False, "Expected HTTPException"


def test_update_incident_builds_set_and_push(fake_mongo):

    oid = ObjectId()

    async def run():

        payload = {
            "_id": str(oid),
            "title": "New title",
            "events": ["e1", "e2"],
            "notes": [{"author": "a", "timestamp": "t", "message": "m"}],
        }

        return await incidentset.update_incident(
            payload=payload,
            request=fake_request(),
            mongo=fake_mongo,
            identity=fake_identity,
        )

    resp = anyio.run(run)

    assert resp == {"updated": True}

    col = fake_mongo._db.collections["incidents"]
    update = col.last_update_one["update"]

    assert "$set" in update
    assert "$push" in update