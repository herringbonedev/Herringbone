from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
import os

from modules.database.mongo_db import HerringboneMongoDatabase

router = APIRouter(prefix="/herringbone/logs", tags=["logs"])


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


def encode(obj):
    return jsonable_encoder(
        obj,
        custom_encoder={ObjectId: lambda x: str(x)},
    )


def merge_parse_results(mongo, event_ids):
    """
    Build {event_id: {field: [values]}} from parse_results
    """
    results = mongo.find(
        collection="parse_results",
        filter_query={"event_id": {"$in": event_ids}},
    )

    parsed_map = {}

    for r in results:
        eid = r.get("event_id")
        if not eid:
            continue

        parsed_map.setdefault(eid, {})

        for k, values in (r.get("results") or {}).items():
            parsed_map[eid].setdefault(k, []).extend(values)

    return parsed_map


@router.get("/events")
def list_events(n: int = Query(25, ge=1, le=500)):
    mongo = get_mongo()

    events = mongo.find_sorted(
        collection="events",
        filter_query={},
        sort=[("_id", -1)],
        limit=n,
    )
    
    if not events:
        return JSONResponse(content=[])

    event_ids = [e["_id"] for e in events]

    states = mongo.find(
        collection="event_state",
        filter_query={"event_id": {"$in": event_ids}},
    )
    state_map = {s["event_id"]: s for s in states if "event_id" in s}

    parsed_map = merge_parse_results(mongo, event_ids)

    for e in events:
        eid = e["_id"]
        e["state"] = state_map.get(eid, {})
        e["parsed"] = parsed_map.get(eid, {})

    return JSONResponse(content=encode(events))


@router.get("/events/{event_id}")
def get_event(event_id: str):
    mongo = get_mongo()

    oid = ObjectId(event_id)

    event = mongo.find_one(
        collection="events",
        filter_query={"_id": oid},
    )

    if not event:
        return JSONResponse(status_code=404, content={"detail": "Event not found"})

    state = mongo.find_one(
        collection="event_state",
        filter_query={"event_id": oid},
    )
    event["state"] = state or {}

    parsed_map = merge_parse_results(mongo, [oid])
    event["parsed"] = parsed_map.get(oid, {})

    return JSONResponse(content=encode(event))


@router.get("/livez")
def livez():
    return {"status": "ok"}


@router.get("/readyz")
def readyz():
    try:
        mongo = get_mongo()
        mongo.find_one(collection="events", filter_query={})
        return {"ready": True}
    except Exception:
        return {"ready": False}
