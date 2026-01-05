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

    if "rule_id" not in payload:
        raise HTTPException(status_code=400, detail="Missing rule_id in detection")

    rule_id = payload["rule_id"]

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=30)

    try:
        candidate = mongo.coll.find_one(
            {
                "status": {"$in": ["open", "investigating"]},
                "rule_id": rule_id,
                "last_updated": {"$gte": window_start},
            },
            sort=[("last_updated", -1)],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if candidate:
        return {
            "action": "attach",
            "incident_id": str(candidate["_id"]),
            "reason": "matching_rule_id_within_window",
        }

    return {
        "action": "create",
        "reason": "no_matching_open_incident",
    }
