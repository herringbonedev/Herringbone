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
AUTO_DISCOVER_CONTEXTS = os.environ.get("AUTO_DISCOVER_CONTEXTS", "false").lower() == "true"

def utcnow():
    return datetime.now(timezone.utc)


def find_next_context_id() -> str:
    if AUTO_DISCOVER_CONTEXTS:
        try:
            bulk = mongo_bulk()
            row = bulk.find_next_context_with_work(
                os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state"),
                {"parsed": True, "detected": False},
                oldest_field="created_at",
            )
            if row and row.get("context_id"):
                return row["context_id"]
        except Exception as e:
            print(f"[WARN] detector context discovery failed: {e}")

    return DEFAULT_CONTEXT_ID


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
    context_id = find_next_context_id()
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


def _all_event_id_forms(event_id: Any) -> list[Any]:
    """
    Return both string and ObjectId forms for event lookups. Herringbone has
    historically stored event linkage as either events._id ObjectId, stringified
    ObjectId, event_id, or event_object_id depending on service/version.
    """
    forms = []
    if event_id is None:
        return forms

    forms.append(event_id)
    forms.append(str(event_id))

    if isinstance(event_id, str) and ObjectId.is_valid(event_id):
        forms.append(ObjectId(event_id))

    normalized = normalize_event_lookup_id(event_id)
    forms.append(normalized)
    forms.append(str(normalized))

    out = []
    seen = set()
    for item in forms:
        key = f"{type(item).__name__}:{item}"
        if key not in seen:
            out.append(item)
            seen.add(key)
    return out


def fetch_parse_results_for_statuses(statuses: list[dict], context_id: str) -> dict[str, dict]:
    """
    Load parser output for the claimed events and return:
        {str(event_id): {field: [values...]}}

    Detector was waiting for event_state.parsed=True, but only sent the raw
    event document to the matcher. That meant rules targeting parsed fields
    such as parsed.command, parsed.run_as, etc. could never match even though
    parse_results contained the expected values.
    """
    collection = os.environ.get("PARSE_RESULTS_COLLECTION", "parse_results")
    raw_event_ids = [s.get("event_id") for s in statuses if s.get("event_id") is not None]

    lookup_ids = []
    seen = set()
    for eid in raw_event_ids:
        for form in _all_event_id_forms(eid):
            key = f"{type(form).__name__}:{form}"
            if key not in seen:
                lookup_ids.append(form)
                seen.add(key)

    if not lookup_ids:
        return {}

    query = {
        "$or": [
            {"event_id": {"$in": lookup_ids}},
            {"event_object_id": {"$in": lookup_ids}},
        ]
    }

    try:
        mongo = mongo_db()
        rows = mongo.find_with_context(collection, query, context_id=context_id)
    except Exception as e:
        print(f"[WARN] detector parse_results fetch unavailable: {e}")
        rows = []

    parsed_by_event: dict[str, dict] = {}
    seen_docs: set[str] = set()

    for row in rows or []:
        doc_id = str(row.get("_id"))
        if doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)

        event_refs = []
        for ref in (row.get("event_id"), row.get("event_object_id")):
            if ref is not None:
                event_refs.extend(_all_event_id_forms(ref))

        if not event_refs:
            continue

        for event_ref in event_refs:
            key = str(event_ref)
            parsed = parsed_by_event.setdefault(key, {})

            for field, values in (row.get("results") or {}).items():
                dest = parsed.setdefault(field, [])
                incoming = values if isinstance(values, list) else [values]
                for value in incoming:
                    if value not in dest:
                        dest.append(value)

    return parsed_by_event


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
