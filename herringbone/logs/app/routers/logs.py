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


def _id_forms(value):
    forms = []

    if value is None:
        return forms

    forms.append(value)
    forms.append(str(value))

    if isinstance(value, str) and ObjectId.is_valid(value):
        forms.append(ObjectId(value))

    out = []
    seen = set()

    for item in forms:
        key = f"{type(item).__name__}:{item}"
        if key not in seen:
            out.append(item)
            seen.add(key)

    return out


def _many_id_forms(values):
    out = []
    seen = set()

    for value in values or []:
        for item in _id_forms(value):
            key = f"{type(item).__name__}:{item}"
            if key not in seen:
                out.append(item)
                seen.add(key)

    return out


def _event_key(value):
    return str(value) if value is not None else ""


def _safe_dt(value):
    if isinstance(value, datetime):
        return value
    return None


def _safe_severity(value):
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _event_time(event):
    return (
        event.get("ingested_at")
        or event.get("timestamp")
        or event.get("created_at")
        or event.get("@timestamp")
    )


def _source_value(event):
    source = event.get("source")
    if source is None:
        return None
    return source


def _rule_id_from_detection(detection):
    return (
        detection.get("rule_id")
        or detection.get("rule")
        or detection.get("rule_name")
        or detection.get("name")
    )


def _detection_title(detection):
    return (
        detection.get("title")
        or detection.get("name")
        or detection.get("rule_name")
        or detection.get("rule_id")
        or "Detection"
    )


def _get_raw_preview(event, limit=240):
    raw = event.get("raw") or event.get("message") or event.get("event")
    if raw is None:
        return None
    raw = str(raw)
    return raw if len(raw) <= limit else raw[:limit] + "..."


def _query_by_event_ids(mongo, collection, event_ids, context_id, extra_filter=None):
    lookup_ids = _many_id_forms(event_ids)

    if not lookup_ids:
        return []

    query = {"event_id": {"$in": lookup_ids}}
    if extra_filter:
        query.update(extra_filter)

    return mongo.find_with_context(
        collection=collection,
        filter_query=query,
        context_id=context_id,
    )


def merge_parse_results(mongo, event_ids, context_id):
    results = _query_by_event_ids(mongo, "parse_results", event_ids, context_id)

    parsed_map = {}

    for r in results:
        eid = r.get("event_id")
        if not eid:
            continue

        key = _event_key(eid)
        parsed_map.setdefault(key, {})

        for k, values in (r.get("results") or {}).items():
            if isinstance(values, list):
                parsed_map[key].setdefault(k, []).extend(values)
            else:
                parsed_map[key].setdefault(k, []).append(values)

    return parsed_map


def merge_event_states(mongo, event_ids, context_id):
    states = _query_by_event_ids(mongo, "event_state", event_ids, context_id)
    state_map = {}

    for s in states:
        eid = s.get("event_id")
        if eid is None:
            continue
        state_map[_event_key(eid)] = s

    return state_map


def merge_detections(mongo, event_ids, context_id):
    detections = _query_by_event_ids(mongo, "detections", event_ids, context_id)
    detection_map = {}

    for d in detections:
        eid = d.get("event_id")
        if eid is None:
            continue
        detection_map.setdefault(_event_key(eid), []).append(d)

    return detection_map


def _best_severity(state, detections):
    severity = _safe_severity((state or {}).get("severity"))
    for d in detections or []:
        dsev = _safe_severity(d.get("severity"))
        if dsev is not None:
            severity = max(severity or 0, dsev)
    return severity


def _is_detected(state, detections):
    # Important:
    # state.detected means "detector processed this event".
    # state.detection means "a rule actually matched".
    # Do not count processed/no-finding events as detected.
    return bool((state or {}).get("detection")) or bool(detections)


def apply_enrichment(event, state_map, parsed_map, detection_map):
    event_id = event.get("_id")
    key = _event_key(event_id)

    state = state_map.get(key, {})
    parsed = parsed_map.get(key, {})
    detections = detection_map.get(key, [])

    event["state"] = state
    event["parsed"] = parsed
    event["detections"] = detections

    # Backward-compatible convenience fields.
    if _is_detected(state, detections):
        event["detected"] = True
        event["detection"] = True
        event["state"]["detection"] = True
        event["state"]["detected"] = True
    else:
        event["detected"] = False
        event["detection"] = False

    severity = _best_severity(state, detections)
    if severity is not None:
        event["severity"] = severity
        event["state"]["severity"] = severity

    return event


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

    state_map = merge_event_states(mongo, event_ids, context_id)
    parsed_map = merge_parse_results(mongo, event_ids, context_id)
    detection_map = merge_detections(mongo, event_ids, context_id)

    for e in events:
        apply_enrichment(e, state_map, parsed_map, detection_map)

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

    try:
        oid = ObjectId(event_id)
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid event id"})

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

    state_map = merge_event_states(mongo, [oid], context_id)
    parsed_map = merge_parse_results(mongo, [oid], context_id)
    detection_map = merge_detections(mongo, [oid], context_id)

    apply_enrichment(event, state_map, parsed_map, detection_map)

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

    detections = mongo.find_with_context(
        collection="detections",
        filter_query={"detection": True},
        context_id=context_id,
    )

    detection_by_event = {}
    for d in detections:
        key = _event_key(d.get("event_id"))
        if key:
            detection_by_event.setdefault(key, []).append(d)

    detected = 0
    undetected = 0
    high_severity = 0
    failed = 0
    seen_event_ids = set()

    for s in states:
        key = _event_key(s.get("event_id"))
        if key:
            seen_event_ids.add(key)

        if s.get("error"):
            failed += 1
            continue

        event_detections = detection_by_event.get(key, [])
        is_detected = _is_detected(s, event_detections)

        if is_detected:
            detected += 1
            sev = _best_severity(s, event_detections)
            if (sev or 0) >= 75:
                high_severity += 1
        else:
            undetected += 1

    # Detections can exist even if state was not found by ID type.
    for key, event_detections in detection_by_event.items():
        if key not in seen_event_ids:
            detected += 1
            if any((_safe_severity(d.get("severity")) or 0) >= 75 for d in event_detections):
                high_severity += 1

    audit.log(
        event="dashboard_summary_accessed",
        identity=identity,
        request=request,
        metadata={"context_id": context_id},
    )

    # Keep the old exact response fields. Add optional aliases, but do not remove old ones.
    return {
        "events_24h": events_24h,
        "detected": detected,
        "undetected": undetected,
        "high_severity": high_severity,
        "failed": failed,
        "detections": detected,
        "errors": failed,
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
    state_map = merge_event_states(mongo, event_ids, context_id)
    detection_map = merge_detections(mongo, event_ids, context_id)

    out = []
    for e in events:
        key = _event_key(e["_id"])
        state = state_map.get(key, {})
        detections = detection_map.get(key, [])
        detected = _is_detected(state, detections)
        severity = _best_severity(state, detections)

        out.append({
            # Old fields
            "event_id": str(e["_id"]),
            "ingested_at": _event_time(e),
            "source": _source_value(e),
            "detected": detected,
            "severity": severity,
            "error": state.get("error"),

            # Extra safe fields for newer dashboards
            "detection": detected,
            "raw": _get_raw_preview(e),
            "card": e.get("card"),
            "state": state,
            "detections": detections,
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

    event_ids = [d.get("event_id") for d in detections if d.get("event_id") is not None]
    events_by_key = {}

    # Best effort event join for dashboard cards.
    if event_ids:
        lookup_ids = _many_id_forms(event_ids)
        try:
            events = mongo.find_with_context(
                collection="events",
                filter_query={"_id": {"$in": lookup_ids}},
                context_id=context_id,
            )
            events_by_key = {_event_key(e.get("_id")): e for e in events}
        except Exception:
            events_by_key = {}

    out = []
    for d in detections:
        key = _event_key(d.get("event_id"))
        event = events_by_key.get(key, {})

        out.append({
            # Old fields
            "event_id": d.get("event_id"),
            "severity": d.get("severity"),
            "inserted_at": d.get("inserted_at"),

            # Compatibility/newer-dashboard fields
            "rule_id": _rule_id_from_detection(d),
            "title": _detection_title(d),
            "detected": bool(d.get("detection", True)),
            "detection": bool(d.get("detection", True)),
            "timestamp": d.get("inserted_at"),
            "source": _source_value(event),
            "raw": _get_raw_preview(event),
            "analysis": d.get("analysis"),
        })

    audit.log(
        event="dashboard_recent_detections",
        identity=identity,
        request=request,
        metadata={"count": len(out), "context_id": context_id},
    )

    return encode(out)


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
