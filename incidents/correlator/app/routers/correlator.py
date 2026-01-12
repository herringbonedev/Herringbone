from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
from modules.database.mongo_db import HerringboneMongoDatabase
import os
import json
import requests

router = APIRouter(
    prefix="/incidents/correlator",
    tags=["correlator"],
)


def get_mongo():
    db = HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        collection=os.environ.get("COLLECTION_NAME", "incidents"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )
    db.open_mongo_connection()
    if db.coll is None:
        raise HTTPException(status_code=500, detail="Mongo connection not initialized")
    return db


EVENTS_API_BASE = os.environ.get(
    "EVENTS_API_BASE",
    "http://127.0.0.1:7010/herringbone/logs/events/",
)


def fetch_event(event_id: str):
    try:
        r = requests.get(f"{EVENTS_API_BASE}/{event_id}", timeout=5)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def extract_correlate_values(event: dict, correlate_on: list[str]):
    correlation_identity = {}
    correlation_filters = []

    for path in correlate_on:
        if not path:
            continue

        value = event
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]

        if value is None:
            continue

        parts = path.split(".")

        target = correlation_identity
        for p in parts[:-1]:
            target = target.setdefault(p, {})

        target[parts[-1]] = value

        mongo_field = "correlation_identity." + ".".join(parts)

        if isinstance(value, list):
            v = sorted(set(value))
            correlation_filters.append({mongo_field: {"$all": v}})
        else:
            correlation_filters.append({mongo_field: value})

    print("[*] correlation_identity =", correlation_identity)
    print("[*] correlation_filters =", correlation_filters)

    return correlation_identity, correlation_filters


@router.post("/correlate")
async def correlate(payload: dict, mongo=Depends(get_mongo)):
    print("[*] Correlator invoked")
    print(json.dumps(payload, indent=2, default=str))

    if "rule_id" not in payload:
        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = str(payload["rule_id"])
    correlate_on = payload.get("correlate_on") or []
    event_ids = payload.get("event_ids") or []
    event_id = event_ids[0] if event_ids else None

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=30)

    rule_clauses = [{"rule_id": rule_id}]
    if ObjectId.is_valid(rule_id):
        rule_clauses.append({"rule_id": ObjectId(rule_id)})

    if correlate_on:
        print("[*] Hard correlation enabled")
        print("[*] correlate_on =", correlate_on)

        if not event_id:
            return {"action": "create", "correlation_identity": {}}

        event = fetch_event(event_id)
        if not isinstance(event, dict):
            return {"action": "create", "correlation_identity": {}}

        correlation_identity, correlation_filters = extract_correlate_values(
            event, correlate_on
        )

        if not correlation_filters:
            return {"action": "create", "correlation_identity": {}}

        query = {
            "status": {"$in": ["open", "investigating"]},
            "state.last_updated": {"$gte": window_start},
            "$or": rule_clauses,
            "$and": correlation_filters,
        }

        print("[*] Correlation query")
        print(json.dumps(query, indent=2, default=str))

        candidate = mongo.coll.find_one(
            query,
            sort=[("state.last_updated", -1)],
        )

        if candidate:
            print("[✓] Correlation identity match")
            return {
                "action": "attach",
                "incident_id": str(candidate["_id"]),
            }

        print("[*] No correlation identity match — creating new incident")
        return {
            "action": "create",
            "correlation_identity": correlation_identity,
        }

    print("[*] No correlate_on defined — rule-only correlation")

    query = {
        "status": {"$in": ["open", "investigating"]},
        "state.last_updated": {"$gte": window_start},
        "$or": rule_clauses,
    }

    candidate = mongo.coll.find_one(
        query,
        sort=[("state.last_updated", -1)],
    )

    if candidate:
        return {
            "action": "attach",
            "incident_id": str(candidate["_id"]),
        }

    return {"action": "create"}
