from fastapi import APIRouter, Depends, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger
import os
import json
import requests


correlate_required = require_scopes("incidents:correlate")

router = APIRouter(
    prefix="/incidents/correlator",
    tags=["correlator"],
)

audit = AuditLogger()


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
    )


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

    return correlation_identity, correlation_filters


@router.post("/correlate")
async def correlate(
    payload: dict,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(correlate_required),
):

    if "rule_id" not in payload:
        audit.log(
            event="correlator_invalid_request",
            identity=identity,
            request=request,
            result="failure",
            severity="WARNING",
            metadata={"reason": "missing_rule_id"},
        )
        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = str(payload["rule_id"])
    correlate_on = payload.get("correlate_on") or []
    event_ids = payload.get("event_ids") or []
    event_id = event_ids[0] if event_ids else None

    incidents_collection = os.environ.get("COLLECTION_NAME", "incidents")

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=30)

    rule_clauses = [{"rule_id": rule_id}]
    if ObjectId.is_valid(rule_id):
        rule_clauses.append({"rule_id": ObjectId(rule_id)})

    if correlate_on:

        if not event_id:
            audit.log(
                event="correlator_no_event_for_correlation",
                identity=identity,
                request=request,
                metadata={"rule_id": rule_id},
            )
            return {"action": "create", "correlation_identity": {}}

        event = fetch_event(event_id)

        if not isinstance(event, dict):
            audit.log(
                event="correlator_event_fetch_failed",
                identity=identity,
                request=request,
                result="failure",
                severity="WARNING",
                metadata={"event_id": event_id},
            )
            return {"action": "create", "correlation_identity": {}}

        correlation_identity, correlation_filters = extract_correlate_values(
            event, correlate_on
        )

        if not correlation_filters:
            audit.log(
                event="correlator_no_correlation_values",
                identity=identity,
                request=request,
                metadata={"rule_id": rule_id},
            )
            return {"action": "create", "correlation_identity": {}}

        query = {
            "status": {"$in": ["open", "investigating"]},
            "state.last_updated": {"$gte": window_start},
            "$or": rule_clauses,
            "$and": correlation_filters,
        }

        try:
            candidates = mongo.find_sorted(
                collection=incidents_collection,
                filter_query=query,
                sort=[("state.last_updated", -1)],
                limit=1,
            )
        except Exception as e:
            audit.log(
                event="correlator_query_failed",
                identity=identity,
                request=request,
                result="failure",
                severity="ERROR",
                metadata={"error": str(e)},
            )
            raise HTTPException(status_code=500, detail=str(e))

        if candidates:
            incident_id = str(candidates[0]["_id"])

            audit.log(
                event="correlator_attach_incident",
                identity=identity,
                request=request,
                target=incident_id,
                metadata={"rule_id": rule_id},
            )

            return {
                "action": "attach",
                "incident_id": incident_id,
            }

        audit.log(
            event="correlator_create_incident",
            identity=identity,
            request=request,
            metadata={"rule_id": rule_id},
        )

        return {
            "action": "create",
            "correlation_identity": correlation_identity,
        }

    query = {
        "status": {"$in": ["open", "investigating"]},
        "state.last_updated": {"$gte": window_start},
        "$or": rule_clauses,
    }

    try:
        candidates = mongo.find_sorted(
            collection=incidents_collection,
            filter_query=query,
            sort=[("state.last_updated", -1)],
            limit=1,
        )
    except Exception as e:
        audit.log(
            event="correlator_query_failed",
            identity=identity,
            request=request,
            result="failure",
            severity="ERROR",
            metadata={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=str(e))

    if candidates:
        incident_id = str(candidates[0]["_id"])

        audit.log(
            event="correlator_attach_incident",
            identity=identity,
            request=request,
            target=incident_id,
            metadata={"rule_id": rule_id},
        )

        return {
            "action": "attach",
            "incident_id": incident_id,
        }

    audit.log(
        event="correlator_create_incident",
        identity=identity,
        request=request,
        metadata={"rule_id": rule_id},
    )

    return {"action": "create"}