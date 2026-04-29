from fastapi import APIRouter, Query, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta, UTC
from bson import ObjectId
import os

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes, get_context
from modules.audit.logger import AuditLogger

router = APIRouter(
    prefix="/herringbone/logs",
    tags=["logs"],
    dependencies=[Depends(get_context)],
)


def events_get_auth(context=Depends(get_context)):
    require_scopes("logs:read")(context)
    return context


def dashboard_auth(context=Depends(get_context)):
    require_scopes("dashboard:read")(context)
    return context


audit = AuditLogger()


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


def merge_parse_results(mongo, event_ids, context_id):
    results = mongo.find_with_context(
        collection="parse_results",
        filter_query={"event_id": {"$in": event_ids}},
        context_id=context_id,
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
    request: Request,
    n: int = Query(25, ge=1, le=500),
    context=Depends(events_get_auth),
):

    identity = context["identity"]
    context_id = context.get("context_id")
    mongo = get_mongo()

    events = mongo.find_sorted_with_context(
        collection="events",
        filter_query={},
        context_id=context_id,
        sort=[("_id", -1)],
        limit=n,
    )

    if not events:
        audit.log(
            event="events_list_accessed",
            identity=identity,
            request=request,
            metadata={"count": 0, "context_id": context_id},
        )
        return JSONResponse(content=[])

    event_ids = [e["_id"] for e in events]

    states = mongo.find_with_context(
        collection="event_state",
        filter_query={"event_id": {"$in": event_ids}},
        context_id=context_id,
    )
    state_map = {s["event_id"]: s for s in states if "event_id" in s}

    parsed_map = merge_parse_results(mongo, event_ids, context_id)

    for e in events:
        eid = e["_id"]
        e["state"] = state_map.get(eid, {})
        e["parsed"] = parsed_map.get(eid, {})

    audit.log(
        event="events_list_accessed",
        identity=identity,
        request=request,
        metadata={"count": len(events), "context_id": context_id},
    )

    return JSONResponse(content=encode(events))


@router.get("/events/{event_id}")
def get_event(
    event_id: str,
    request: Request,
    context=Depends(events_get_auth),
):

    identity = context["identity"]
    context_id = context.get("context_id")
    mongo = get_mongo()
    oid = ObjectId(event_id)

    event = mongo.find_one_with_context(
        collection="events",
        filter_query={"_id": oid},
        context_id=context_id,
    )

    if not event:
        audit.log(
            event="event_lookup_failed",
            identity=identity,
            request=request,
            target=str(event_id),
            result="failure",
            severity="WARNING",
            metadata={"context_id": context_id},
        )
        return JSONResponse(status_code=404, content={"detail": "Event not found"})

    state = mongo.find_one_with_context(
        collection="event_state",
        filter_query={"event_id": oid},
        context_id=context_id,
    )
    event["state"] = state or {}

    parsed_map = merge_parse_results(mongo, [oid], context_id)
    event["parsed"] = parsed_map.get(oid, {})

    audit.log(
        event="event_lookup",
        identity=identity,
        request=request,
        target=str(event_id),
        metadata={"context_id": context_id},
    )

    return JSONResponse(content=encode(event))


@router.get("/dashboard/summary")
def dashboard_summary(
    request: Request,
    context=Depends(dashboard_auth),
):
    identity = context["identity"]
    context_id = context.get("context_id")
    mongo = get_mongo()
    now = datetime.now(UTC)
    since = now - timedelta(hours=24)

    events = mongo.find_with_context(
        collection="events",
        filter_query={"ingested_at": {"$gte": since}},
        context_id=context_id,
    )
    events_24h = len(events)

    states = mongo.find_with_context(
        collection="event_state",
        filter_query={},
        context_id=context_id,
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

    audit.log(
        event="dashboard_summary_accessed",
        identity=identity,
        request=request,
        metadata={"context_id": context_id},
    )

    return {
        "events_24h": events_24h,
        "detected": detected,
        "undetected": undetected,
        "high_severity": high_severity,
        "failed": failed,
    }


@router.get("/dashboard/recent-events")
def dashboard_recent_events(
    request: Request,
    n: int = Query(10, ge=1, le=50),
    context=Depends(dashboard_auth),
):

    identity = context["identity"]
    context_id = context.get("context_id")
    mongo = get_mongo()

    events = mongo.find_sorted_with_context(
        collection="events",
        filter_query={},
        context_id=context_id,
        sort=[("_id", -1)],
        limit=n,
    )

    if not events:
        audit.log(
            event="dashboard_recent_events",
            identity=identity,
            request=request,
            metadata={"count": 0, "context_id": context_id},
        )
        return []

    event_ids = [e["_id"] for e in events]

    states = mongo.find_with_context(
        collection="event_state",
        filter_query={"event_id": {"$in": event_ids}},
        context_id=context_id,
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

    audit.log(
        event="dashboard_recent_events",
        identity=identity,
        request=request,
        metadata={"count": len(out), "context_id": context_id},
    )

    return encode(out)


@router.get("/dashboard/recent-detections")
def dashboard_recent_detections(
    request: Request,
    n: int = Query(10, ge=1, le=50),
    context=Depends(dashboard_auth),
):

    identity = context["identity"]
    context_id = context.get("context_id")
    mongo = get_mongo()

    detections = mongo.find_sorted_with_context(
        collection="detections",
        filter_query={"detection": True},
        context_id=context_id,
        sort=[("inserted_at", -1)],
        limit=n,
    )

    audit.log(
        event="dashboard_recent_detections",
        identity=identity,
        request=request,
        metadata={"count": len(detections), "context_id": context_id},
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
    request: Request,
    n: int = Query(10, ge=1, le=50),
    context=Depends(dashboard_auth),
):

    identity = context["identity"]
    context_id = context.get("context_id")
    mongo = get_mongo()

    incidents = mongo.find_sorted_with_context(
        collection="incidents",
        filter_query={},
        context_id=context_id,
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

    audit.log(
        event="dashboard_recent_incidents",
        identity=identity,
        request=request,
        metadata={"count": len(results), "context_id": context_id},
    )

    return JSONResponse(content=encode(results))


@router.get("/dashboard/incidents-throughput")
def incidents_throughput(
    request: Request,
    days: int = Query(7, ge=1, le=30),
    context=Depends(dashboard_auth),
):

    identity = context["identity"]
    context_id = context.get("context_id")
    mongo = get_mongo()

    since = datetime.now(UTC) - timedelta(days=days)

    incidents = mongo.find_with_context(
        collection="incidents",
        filter_query={"created_at": {"$gte": since}},
        context_id=context_id,
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

    audit.log(
        event="dashboard_incidents_throughput",
        identity=identity,
        request=request,
        metadata={"count": len(result), "context_id": context_id},
    )

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