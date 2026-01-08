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
        print("[✗] Missing rule_id")
        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = str(payload["rule_id"])
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=30)

    clauses = [{"rule_id": rule_id}]
    if ObjectId.is_valid(rule_id):
        clauses.append({"rule_id": ObjectId(rule_id)})

    query = {
        "status": {"$in": ["open", "investigating"]},
        "$or": clauses,
        "state.last_updated": {"$gte": window_start},
    }

    print("[*] Correlation query")
    print(json.dumps(query, indent=2, default=str))

    candidate = mongo.coll.find_one(query, sort=[("state.last_updated", -1)])

    if candidate:
        print("[✓] Matching incident found")
        print(json.dumps(candidate, indent=2, default=str))
        return {"action": "attach", "incident_id": str(candidate["_id"])}

    print("[✗] No matching incident")
    return {"action": "create"}
