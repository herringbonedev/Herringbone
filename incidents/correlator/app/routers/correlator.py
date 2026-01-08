from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
from modules.database.mongo_db import HerringboneMongoDatabase
import os
import json

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


@router.post("/correlate")
async def correlate(payload: dict, mongo=Depends(get_mongo)):
    print("[*] Correlator invoked")
    print(json.dumps(payload, indent=2, default=str))

    if "rule_id" not in payload:
        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = str(payload["rule_id"])
    correlate_on = payload.get("correlate_on") or []
    event = payload.get("event")

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=30)

    rule_clauses = [{"rule_id": rule_id}]
    if ObjectId.is_valid(rule_id):
        rule_clauses.append({"rule_id": ObjectId(rule_id)})

    if correlate_on:
        if not isinstance(event, dict):
            return {
                "action": "create",
                "correlation_identity": {},
            }

        correlation_filters = []
        correlation_identity = {}

        for field in correlate_on:
            parts = field.split(".")
            value = event
            for p in parts:
                if not isinstance(value, dict) or p not in value:
                    value = None
                    break
                value = value[p]

            if value is None:
                return {
                    "action": "create",
                    "correlation_identity": {},
                }

            if isinstance(value, list):
                value = sorted(set(value))
                correlation_filters.append({field: {"$all": value}})
            else:
                correlation_filters.append({field: value})

            correlation_identity[field] = value

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
            return {
                "action": "attach",
                "incident_id": str(candidate["_id"]),
            }

        return {
            "action": "create",
            "correlation_identity": correlation_identity,
        }

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

    return {
        "action": "create",
    }
