from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from bson import ObjectId
from bson.json_util import dumps

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger

from app.schema import IncidentSchema

import os
import json


incident_writer = require_scopes("incidents:write")
incident_reader = require_scopes("incidents:read")


router = APIRouter(
    prefix="/incidents/incidentset",
    tags=["incidentset"],
)

validator = IncidentSchema()
audit = AuditLogger()


class IncidentBase(BaseModel):
    model_config = ConfigDict(extra="allow")


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
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_writer),
):

    data = payload.model_dump()
    now = datetime.now(timezone.utc)

    data["created_at"] = now
    data["last_updated"] = now
    data["state"] = {"last_updated": now}
    data["status"] = data.get("status", "open")

    validation = validator(data)

    if not validation["valid"]:

        audit.log(
            event="incident_insert_validation_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata=validation,
        )

        raise HTTPException(status_code=400, detail=validation)

    try:

        mongo.insert_one(incidents_collection(), data)

        audit.log(
            event="incident_inserted",
            identity=identity,
            request=request,
            target=data.get("title"),
            metadata={"status": data["status"]},
        )

    except Exception as e:

        audit.log(
            event="incident_insert_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e)},
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))

    return {"inserted": True}


@router.post("/update_incident")
async def update_incident(
    payload: dict,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_writer),
):

    raw_id = payload.pop("_id", None)

    if not raw_id:

        audit.log(
            event="incident_update_missing_id",
            identity=identity,
            request=request,
            result="failure",
        )

        raise HTTPException(status_code=400, detail="Missing _id")

    try:
        oid = ObjectId(raw_id if isinstance(raw_id, str) else raw_id.get("$oid"))
    except Exception:

        audit.log(
            event="incident_update_invalid_id",
            identity=identity,
            request=request,
            target=str(raw_id),
            result="failure",
        )

        raise HTTPException(status_code=400, detail="Invalid _id")

    now = datetime.now(timezone.utc)

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

    try:

        client, db = mongo.open_mongo_connection()
        collection = db[incidents_collection()]

        result = collection.update_one(
            {"_id": oid},
            update_doc,
            upsert=True,
        )

        audit.log(
            event="incident_updated",
            identity=identity,
            request=request,
            target=str(oid),
            metadata={"modified_count": result.modified_count},
        )

    except Exception as e:

        audit.log(
            event="incident_update_failed",
            identity=identity,
            request=request,
            target=str(oid),
            result="failure",
            metadata={"error": str(e)},
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))

    finally:
        mongo.close_mongo_connection()

    return {"updated": True}


@router.get("/get_incidents")
async def get_incidents(
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_reader),
):

    try:

        docs = mongo.find(incidents_collection(), {})

        audit.log(
            event="incident_list_accessed",
            identity=identity,
            request=request,
        )

        return JSONResponse(content=json.loads(dumps(docs)))

    except Exception as e:

        audit.log(
            event="incident_list_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e)},
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_incident/{incident_id}")
async def get_incident(
    incident_id: str,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_reader),
):

    try:
        oid = ObjectId(incident_id)
    except Exception:

        audit.log(
            event="incident_lookup_invalid_id",
            identity=identity,
            request=request,
            target=incident_id,
            result="failure",
        )

        raise HTTPException(status_code=400, detail="Invalid incident id")

    try:
        doc = mongo.find_one(incidents_collection(), {"_id": oid})
    except Exception as e:

        audit.log(
            event="incident_lookup_failed",
            identity=identity,
            request=request,
            target=incident_id,
            result="failure",
            metadata={"error": str(e)},
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))

    if not doc:

        audit.log(
            event="incident_lookup_not_found",
            identity=identity,
            request=request,
            target=incident_id,
            result="failure",
        )

        raise HTTPException(status_code=404, detail="Incident not found")

    audit.log(
        event="incident_lookup_success",
        identity=identity,
        request=request,
        target=incident_id,
    )

    return JSONResponse(content=json.loads(dumps(doc)))