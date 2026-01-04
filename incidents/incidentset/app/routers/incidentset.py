from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from bson.json_util import dumps
from modules.database.mongo_db import HerringboneMongoDatabase
from schema import IncidentSchema
import os
import json

router = APIRouter(
    prefix="/incidents/incidentset",
    tags=["incidentset"],
)

validator = IncidentSchema()


class IncidentBase(BaseModel):
    """
    Base model for an incident.
    Allows arbitrary extra fields so the incident schema can evolve.
    """
    class Config:
        extra = "allow"


class IncidentCreate(IncidentBase):
    """
    Payload for creating a new incident.
    Inherits all fields from IncidentBase.
    """
    pass


class IncidentUpdate(IncidentBase):
    """
    Update payload for incidents.
    Accepts '_id' from the client but stores it as 'id'.
    """
    id: str = Field(..., alias="_id", serialization_alias="_id")


def get_mongo():
    """
    Returns an initialized HerringboneMongoDatabase instance.
    Ensures the Mongo collection is available before each request.
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


@router.post("/insert_incident")
async def insert_incident(payload: IncidentCreate, mongo=Depends(get_mongo)):
    """
    Inserts a new incident.
    Uses Pydantic for basic shape and IncidentSchema for custom validation.
    """
    data = payload.dict()

    validation = validator(data)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON", "details": validation["error"]},
        )

    try:
        mongo.insert_log(data)
    except Exception:
        raise HTTPException(status_code=500, detail={"inserted": False})

    return {"inserted": True}


@router.get("/get_incidents")
async def get_incidents(mongo=Depends(get_mongo)):
    """
    Returns all incidents from MongoDB as raw JSON.
    """
    try:
        docs = list(mongo.coll.find({}))
        return JSONResponse(content=json.loads(dumps(docs)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/delete_incident")
async def delete_incident(id: str = Query(None), mongo=Depends(get_mongo)):
    """
    Deletes an incident by MongoDB ObjectId passed as a query parameter 'id'.
    """
    if not id:
        raise HTTPException(status_code=400, detail="id is required")

    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    try:
        result = mongo.coll.delete_one({"_id": oid})
    except Exception:
        raise HTTPException(status_code=500, detail={"deleted": False})

    return {"deleted": result.deleted_count > 0}


@router.post("/update_incident")
async def update_incident(payload: dict, mongo=Depends(get_mongo)):
    if "_id" not in payload:
        raise HTTPException(status_code=400, detail="Missing incident _id")

    raw_id = payload.pop("_id")

    if isinstance(raw_id, dict) and "$oid" in raw_id:
        incident_id = raw_id["$oid"]
    else:
        incident_id = raw_id

    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    # Only allow mutable fields
    update_fields = {}
    for key in ("owner", "status", "priority"):
        if key in payload:
            update_fields[key] = payload[key]

    if not update_fields:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    # Validate only the mutable fields
    validation = validator({
        "title": "placeholder",
        "status": update_fields.get("status", "open"),
        "priority": update_fields.get("priority", "low"),
    })
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON", "details": validation["error"]},
        )

    try:
        result = mongo.coll.update_one(
            {"_id": oid},
            {"$set": update_fields},
        )
    except Exception:
        raise HTTPException(status_code=500, detail={"updated": False})

    return {"updated": result.modified_count > 0}


@router.get("/get_incident")
async def get_incident(id: str = Query(None), mongo=Depends(get_mongo)):
    """
    Returns a single incident by MongoDB ObjectId passed as a query parameter 'id'.
    """
    if not id:
        raise HTTPException(status_code=400, detail="id is required")

    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    try:
        doc = mongo.coll.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Incident not found")

        return JSONResponse(content=json.loads(dumps(doc)))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/livez")
async def livez():
    """
    Liveness probe endpoint.
    """
    return "OK"


@router.get("/readyz")
async def readyz():
    """
    Readiness probe endpoint.
    Ensures MongoDB is reachable.
    """
    try:
        _ = get_mongo()
        return {"ready": True}
    except Exception:
        return JSONResponse(content={"ready": False}, status_code=503)
