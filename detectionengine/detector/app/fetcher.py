import os
import socket
from datetime import datetime, timezone, timedelta
from typing import Any

from bson import ObjectId

from app.dbutil import mongo_db, mongo_bulk


DEFAULT_CONTEXT_ID = os.environ.get("CONTEXT_ID", "default")
INSTANCE_ID = os.environ.get("HOSTNAME") or socket.gethostname()
CLAIM_LEASE_SECONDS = int(os.environ.get("DETECTOR_CLAIM_LEASE_SECONDS", 300))
INCLUDE_MISSING_DEFAULT_CONTEXT = os.environ.get("INCLUDE_MISSING_DEFAULT_CONTEXT", "false").lower() == "true"


def utcnow():
    return datetime.now(timezone.utc)


def normalize_event_lookup_id(event_id: Any):
    if isinstance(event_id, ObjectId):
        return event_id
    if isinstance(event_id, str) and ObjectId.is_valid(event_id):
        return ObjectId(event_id)
    return event_id


def event_lookup_keys(event_id: Any) -> list[str]:
    keys = []
    if event_id is not None:
        keys.append(str(event_id))
        normalized = normalize_event_lookup_id(event_id)
        keys.append(str(normalized))
    return list(dict.fromkeys(keys))


def _claimable_filter():
    now = utcnow()
    return {
        "$or": [
            {"detection_claimed": False},
            {"detection_claimed": {"$exists": False}},
            {"detection_lease_expires_at": {"$lt": now}},
        ]
    }


def claim_batch_undetected(limit: int | None = None) -> list[dict]:
    status_collection = os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state")
    context_id = DEFAULT_CONTEXT_ID
    limit = max(1, int(limit or os.environ.get("DETECTOR_BATCH_SIZE", 100)))

    claim_patch = {
        "detection_claimed": True,
        "detection_claimed_by": INSTANCE_ID,
        "detection_claimed_at": utcnow(),
        "detection_lease_expires_at": utcnow() + timedelta(seconds=CLAIM_LEASE_SECONDS),
    }

    try:
        bulk = mongo_bulk()
        states = bulk.claim_batch(
            status_collection,
            {"parsed": True, "detected": False},
            claim_patch,
            context_id=context_id,
            limit=limit,
            sort=[("created_at", 1), ("_id", 1)],
            claimable_filter=_claimable_filter(),
            claimed_by_field="detection_claimed_by",
            include_missing_default_context=INCLUDE_MISSING_DEFAULT_CONTEXT,
        )
    except Exception as e:
        # Fallback keeps old behavior alive if mongodb_bulk.py is not present/new enough.
        print(f"[WARN] detector bulk claim unavailable, using wrapper fallback: {e}")
        mongo = mongo_db()
        states = mongo.find_sorted(
            collection=status_collection,
            filter_query={"parsed": True, "detected": False, "context_id": context_id},
            sort=[("_id", 1)],
            limit=limit,
        )

    for state in states or []:
        state["context_id"] = state.get("context_id") or context_id

    return states or []


def fetch_events_for_statuses(statuses: list[dict], context_id: str) -> dict[str, dict]:
    events_collection = os.environ.get("EVENTS_COLLECTION_NAME", "events")
    raw_event_ids = [s.get("event_id") for s in statuses if s.get("event_id") is not None]
    lookup_ids = [normalize_event_lookup_id(eid) for eid in raw_event_ids]

    if not lookup_ids:
        return {}

    try:
        bulk = mongo_bulk()
        events = bulk.find_many_by_ids(
            events_collection,
            lookup_ids,
            context_id=context_id,
            id_field="_id",
            preserve_order=False,
            include_missing_default_context=False,
        )
    except Exception as e:
        print(f"[WARN] detector bulk event fetch unavailable, using wrapper fallback: {e}")
        mongo = mongo_db()
        events = []
        for lookup_id in lookup_ids:
            event = mongo.find_one_with_context(events_collection, {"_id": lookup_id}, context_id=context_id)
            if event:
                events.append(event)

    by_key = {}
    for event in events or []:
        eid = event.get("_id")
        if eid is not None:
            by_key[str(eid)] = event

    return by_key


def release_claims(statuses: list[dict], context_id: str, reason: str = "released"):
    if not statuses:
        return 0

    status_ids = [s.get("_id") for s in statuses if s.get("_id") is not None]
    if not status_ids:
        return 0

    status_collection = os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state")
    patch = {
        "detection_claimed": False,
        "detection_claimed_by": "",
        "detection_lease_expires_at": None,
        "detection_last_error": reason,
        "detection_last_error_at": utcnow(),
    }

    try:
        bulk = mongo_bulk()
        return bulk.release_batch_by_ids(
            status_collection,
            status_ids,
            patch,
            context_id=context_id,
            id_field="_id",
            include_missing_default_context=INCLUDE_MISSING_DEFAULT_CONTEXT,
        )
    except Exception as e:
        print(f"[WARN] detector bulk release unavailable: {e}")
        return 0


def fetch_one_undetected() -> dict | None:
    statuses = claim_batch_undetected(1)
    if not statuses:
        return None

    status = statuses[0]
    context_id = status.get("context_id") or DEFAULT_CONTEXT_ID
    events_by_id = fetch_events_for_statuses(statuses, context_id)

    event = None
    for key in event_lookup_keys(status.get("event_id")):
        event = events_by_id.get(key)
        if event:
            break

    if not event:
        release_claims(statuses, context_id, "event_not_found")
        return None

    return {"event": event, "status": status, "context_id": context_id}
