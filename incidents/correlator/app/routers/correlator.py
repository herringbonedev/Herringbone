from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.json_util import dumps
from datetime import datetime, timedelta
from modules.database.mongo_db import HerringboneMongoDatabase
import os
import json

router = APIRouter(
    prefix="/incidents/correlator",
    tags=["correlator"],
)


def get_mongo():
    """
    Returns an initialized HerringboneMongoDatabase instance.
    Uses the incidents collection for correlation lookups.
    """
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
    print("[*] Incoming payload:")
    print(json.dumps(payload, indent=2, default=str))

    if "rule_id" not in payload:
        print("[✗] Missing rule_id in payload")
        raise HTTPException(status_code=400, detail="Missing rule_id in detection")

    rule_id_raw = payload["rule_id"]
    rule_id_str = str(rule_id_raw)

    print(f"[*] rule_id (raw): {rule_id_raw} ({type(rule_id_raw)})")
    print(f"[*] rule_id (str): {rule_id_str}")

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=30)

    print(f"[*] Correlation window start: {window_start.isoformat()}")
    
    rule_id_clauses = [{"rule_id": rule_id_str}]

    if ObjectId.is_valid(rule_id_str):
        rule_id_clauses.append({"rule_id": ObjectId(rule_id_str)})
        print("[*] rule_id is a valid ObjectId — adding ObjectId matcher")
    else:
        print("[*] rule_id is NOT a valid ObjectId")

    query = {
        "status": {"$in": ["open", "investigating"]},
        "$or": rule_id_clauses,
        "state.last_updated": {"$gte": window_start},
    }

    print("[*] Correlation query:")
    print(json.dumps(query, indent=2, default=str))

    try:
        candidate = mongo.coll.find_one(
            query,
            sort=[("state.last_updated", -1)],
        )
    except Exception as e:
        print("[✗] MongoDB query failed")
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))

    if candidate:
        print("[✓] Found matching incident")
        print(json.dumps(candidate, indent=2, default=str))

        return {
            "action": "attach",
            "incident_id": str(candidate["_id"]),
            "reason": "matching_rule_id_within_window",
        }

    print("[✗] No matching incident found")
    print("[*] Performing diagnostic dump of recent incidents")

    # Extra diagnostic: dump recent open incidents
    recent = list(
        mongo.coll.find(
            {"status": {"$in": ["open", "investigating"]}}
        )
        .sort("state.last_updated", -1)
        .limit(5)
    )

    for i, inc in enumerate(recent):
        print(f"[i] Candidate {i}:")
        print(json.dumps({
            "_id": str(inc.get("_id")),
            "rule_id": inc.get("rule_id"),
            "rule_id_type": str(type(inc.get("rule_id"))),
            "status": inc.get("status"),
            "state.last_updated": inc.get("state", {}).get("last_updated"),
        }, indent=2, default=str))

    return {
        "action": "create",
        "reason": "no_matching_open_incident",
    }


