from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId
from bson.json_util import dumps
from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.deps import get_current_user, require_admin
from schema import IncidentSchema
import os
import json

router = APIRouter(
    prefix="/incidents/incidentset",
    tags=["incidentset"],
)

validator = IncidentSchema()


class IncidentBase(BaseModel):
    class Config:
        extra = "allow"


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(IncidentBase):
    id: str = Field(..., alias="_id", serialization_alias="_id")


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


@router.post("/insert_incident")
async def insert_incident(
    payload: IncidentCreate,
    mongo=Depends(get_mongo),
    user=Depends(require_admin),
):
    print("[*] insert_incident called")
    print(json.dumps(payload.dict(), indent=2, default=str))

    data = payload.dict()
    now = datetime.utcnow()

    data["created_at"] = now
    data["last_updated"] = now
    data["state"] = {"last_updated": now}
    data["status"] = data.get("status", "open")

    print("[*] enriched incident")
    print(json.dumps(data, indent=2, default=str))

    validation = validator(data)
    print("[*] validation result")
    print(validation)

    if not validation["valid"]:
        print("[✗] validation failed")
        raise HTTPException(status_code=400, detail=validation)

    mongo.insert_log(data)
    print("[✓] incident inserted")
    return {"inserted": True}


@router.post("/update_incident")
async def update_incident(
    payload: dict,
    mongo=Depends(get_mongo),
    user=Depends(require_admin),
):
    print("[*] update_incident called")
    print(json.dumps(payload, indent=2, default=str))

    raw_id = payload.pop("_id", None)
    if not raw_id:
        raise HTTPException(status_code=400, detail="Missing _id")

    try:
        oid = ObjectId(raw_id if isinstance(raw_id, str) else raw_id.get("$oid"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid _id")

    now = datetime.utcnow()

    set_fields = {
        "last_updated": now,
        "state.last_updated": now,
    }

    push_fields = {}

    for key, value in payload.items():
        if key in ("events", "detections", "notes") and isinstance(value, list):
            push_fields[key] = {"$each": value}
        else:
            set_fields[key] = value

    update_doc = {"$set": set_fields}
    if push_fields:
        update_doc["$push"] = push_fields

    print("[*] update document")
    print(json.dumps(update_doc, indent=2, default=str))

    result = mongo.coll.update_one({"_id": oid}, update_doc)
    print(f"[*] modified_count={result.modified_count}")

    return {"updated": result.modified_count > 0}


@router.get("/get_incidents")
async def get_incidents(
    mongo=Depends(get_mongo),
    user=Depends(get_current_user),
):
    print("[*] get_incidents called")
    docs = list(mongo.coll.find({}))
    print(f"[*] returning {len(docs)} incidents")
    return JSONResponse(content=json.loads(dumps(docs)))


@router.get("/get_incident/{incident_id}")
async def get_incident(
    incident_id: str,
    mongo=Depends(get_mongo),
    user=Depends(get_current_user),
):
    print("[*] get_incident called")
    print(f"[*] incident_id={incident_id}")

    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident id")

    doc = mongo.coll.find_one({"_id": oid})

    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")

    return JSONResponse(content=json.loads(dumps(doc)))

