from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId
from bson.json_util import dumps
from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.user import require_role
from modules.auth.service import require_service_scope
from modules.auth.mix import service_or_role
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
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
    )


def incidents_collection():
    return os.environ.get("COLLECTION_NAME", "incidents")


@router.post("/insert_incident")
async def insert_incident(
    payload: IncidentCreate,
    mongo=Depends(get_mongo),
    auth=Depends(service_or_role("incidents:write", ["admin", "analyst"])),
):
    data = payload.dict()
    now = datetime.utcnow()

    data["created_at"] = now
    data["last_updated"] = now
    data["state"] = {"last_updated": now}
    data["status"] = data.get("status", "open")

    validation = validator(data)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation)

    try:
        mongo.insert_one(incidents_collection(), data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"inserted": True}


import traceback

import traceback

@router.post("/update_incident")
async def update_incident(
    payload: dict, 
    mongo=Depends(get_mongo),
    auth=Depends(service_or_role("incidents:write", ["admin", "analyst"])),
):
    print("\n========== UPDATE INCIDENT ==========")
    print("Raw payload:")
    print(json.dumps(payload, default=str, indent=2))

    raw_id = payload.pop("_id", None)
    if not raw_id:
        raise HTTPException(status_code=400, detail="Missing _id")

    try:
        oid = ObjectId(raw_id if isinstance(raw_id, str) else raw_id.get("$oid"))
        print("Parsed ObjectId:", oid)
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

    print("Generated Mongo update document:")
    print(json.dumps(update_doc, default=str, indent=2))

    try:
        client, db = mongo.open_mongo_connection()

        collection = db[incidents_collection()]

        result = collection.update_one(
            {"_id": oid},
            update_doc,
            upsert=True,
        )

        print("Mongo result:", result.raw_result)

    except Exception as e:
        print("MONGO ERROR:")
        print(str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        mongo.close_mongo_connection()

    print("========== UPDATE COMPLETE ==========\n")

    return {"updated": True}


@router.get("/get_incidents")
async def get_incidents(
    mongo=Depends(get_mongo),
    auth=Depends(service_or_role("incidents:read", ["admin", "analyst"])),
):
    try:
        docs = mongo.find(incidents_collection(), {})
        return JSONResponse(content=json.loads(dumps(docs)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_incident/{incident_id}")
async def get_incident(
    incident_id: str,
    mongo=Depends(get_mongo),
    auth=Depends(service_or_role("incidents:read", ["admin", "analyst"])),
):
    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident id")

    try:
        doc = mongo.find_one(incidents_collection(), {"_id": oid})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")

    return JSONResponse(content=json.loads(dumps(doc)))
