from fastapi import APIRouter, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta
from bson import ObjectId
import os

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.user import get_current_user
from modules.auth.mix import service_or_user

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
def list_events(
    n: int = Query(25, ge=1, le=500),
    auth=Depends(service_or_user("events:get")),
):
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
def get_event(
    event_id: str,
    auth=Depends(service_or_user("events:get")),
):
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


@router.get("/dashboard/summary")
def dashboard_summary(user=Depends(get_current_user)):
    mongo = get_mongo()
    now = datetime.utcnow()
    since = now - timedelta(hours=24)

    events = mongo.find(
        collection="events",
        filter_query={"ingested_at": {"$gte": since}},
    )
    events_24h = len(events)

    states = mongo.find(
        collection="event_state",
        filter_query={},
    )

    detected = 0
    undetected = 0
    high_severity = 0
    failed = 0

    for s in states:
        if s.get("error"):
            failed += 1
            continue

        if s.get("detection"):
            detected += 1
            if (s.get("severity") or 0) >= 75:
                high_severity += 1
        else:
            undetected += 1

    return {
        "events_24h": events_24h,
        "detected": detected,
        "undetected": undetected,
        "high_severity": high_severity,
        "failed": failed,
    }


@router.get("/dashboard/recent-events")
def dashboard_recent_events(
    n: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
):
    mongo = get_mongo()

    events = mongo.find_sorted(
        collection="events",
        filter_query={},
        sort=[("_id", -1)],
        limit=n,
    )

    if not events:
        return []

    event_ids = [e["_id"] for e in events]

    states = mongo.find(
        collection="event_state",
        filter_query={"event_id": {"$in": event_ids}},
    )
    state_map = {s["event_id"]: s for s in states}

    out = []
    for e in events:
        s = state_map.get(e["_id"], {})
        out.append({
            "event_id": str(e["_id"]),
            "ingested_at": e.get("ingested_at"),
            "source": e.get("source"),
            "detected": bool(s.get("detection")),
            "severity": s.get("severity"),
            "error": s.get("error"),
        })

    return encode(out)


@router.get("/dashboard/recent-detections")
def dashboard_recent_detections(
    n: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
):
    mongo = get_mongo()

    detections = mongo.find_sorted(
        collection="detections",
        filter_query={"detection": True},
        sort=[("inserted_at", -1)],
        limit=n,
    )

    return encode([
        {
            "event_id": d.get("event_id"),
            "severity": d.get("severity"),
            "inserted_at": d.get("inserted_at"),
        }
        for d in detections
    ])


@router.get("/dashboard/recent-incidents")
def recent_incidents(
    n: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
):
    mongo = get_mongo()

    incidents = mongo.find_sorted(
        collection="incidents",
        filter_query={},
        sort=[("created_at", -1)],
        limit=n,
    )

    results = []
    for i in incidents:
        results.append({
            "incident_id": str(i.get("_id")),
            "title": i.get("title"),
            "status": i.get("status"),
            "priority": i.get("priority"),
            "owner": i.get("owner"),
            "created_at": i.get("created_at"),
        })

    return JSONResponse(content=encode(results))


@router.get("/dashboard/incidents-throughput")
def incidents_throughput(
    days: int = Query(7, ge=1, le=30),
    user=Depends(get_current_user),
):
    mongo = get_mongo()

    since = datetime.utcnow() - timedelta(days=days)

    incidents = mongo.find(
        collection="incidents",
        filter_query={"created_at": {"$gte": since}},
    )

    buckets = {}

    for i in incidents:
        created = i.get("created_at")
        if not created:
            continue

        day = created.strftime("%Y-%m-%d")
        buckets.setdefault(day, {"open": 0, "resolved": 0})

        if i.get("status") == "resolved":
            buckets[day]["resolved"] += 1
        else:
            buckets[day]["open"] += 1

    result = [
        {"ts": day, **counts}
        for day, counts in sorted(buckets.items())
    ]

    return JSONResponse(content=encode(result))


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
