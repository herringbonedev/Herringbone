from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
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
async def insert_incident(payload: IncidentCreate, mongo=Depends(get_mongo)):
    print("[*] insert_incident called")
    print("[*] raw payload:")
    print(json.dumps(payload.dict(), indent=2, default=str))

    data = payload.dict()

    now = datetime.utcnow()

    data.setdefault("rule_id", payload.dict().get("rule_id"))
    data.setdefault("rule_name", payload.dict().get("rule_name"))

    data["created_at"] = now
    data["last_updated"] = now
    data["status"] = data.get("status", "open")

    data["state"] = {
        "last_updated": now
    }

    print("[*] incident after enrichment:")
    print(json.dumps(data, indent=2, default=str))

    validation = validator(data)
    print("[*] validation result:")
    print(validation)

    if not validation["valid"]:
        print("[✗] validation failed")
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON", "details": validation["error"]},
        )

    try:
        mongo.insert_log(data)
        print("[✓] incident inserted")
    except Exception as e:
        print("[✗] mongo insert failed")
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))

    return {"inserted": True}


@router.get("/get_incidents")
async def get_incidents(mongo=Depends(get_mongo)):
    print("[*] get_incidents called")
    try:
        docs = list(mongo.coll.find({}))
        print(f"[*] returning {len(docs)} incidents")
        return JSONResponse(content=json.loads(dumps(docs)))
    except Exception as e:
        print("[✗] get_incidents failed")
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/delete_incident")
async def delete_incident(id: str = Query(None), mongo=Depends(get_mongo)):
    print(f"[*] delete_incident called id={id}")

    if not id:
        print("[✗] missing id")
        raise HTTPException(status_code=400, detail="id is required")

    try:
        oid = ObjectId(id)
    except Exception:
        print("[✗] invalid ObjectId")
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    try:
        result = mongo.coll.delete_one({"_id": oid})
        print(f"[*] deleted_count={result.deleted_count}")
    except Exception as e:
        print("[✗] delete failed")
        print(str(e))
        raise HTTPException(status_code=500, detail={"deleted": False})

    return {"deleted": result.deleted_count > 0}


@router.post("/update_incident")
async def update_incident(payload: dict, mongo=Depends(get_mongo)):
    print("[*] update_incident called")
    print(json.dumps(payload, indent=2, default=str))

    if "_id" not in payload:
        print("[✗] missing _id")
        raise HTTPException(status_code=400, detail="Missing incident _id")

    raw_id = payload.pop("_id")

    if isinstance(raw_id, dict) and "$oid" in raw_id:
        incident_id = raw_id["$oid"]
    else:
        incident_id = raw_id

    try:
        oid = ObjectId(incident_id)
    except Exception:
        print("[✗] invalid ObjectId")
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    update_fields = {}
    for key in ("owner", "status", "priority"):
        if key in payload:
            update_fields[key] = payload[key]

    print("[*] update_fields:")
    print(update_fields)

    if not update_fields:
        print("[✗] no updatable fields")
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    validation = validator({
        "title": "placeholder",
        "status": update_fields.get("status", "open"),
        "priority": update_fields.get("priority", "low"),
    })

    print("[*] validation result:")
    print(validation)

    if not validation["valid"]:
        print("[✗] validation failed")
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON", "details": validation["error"]},
        )

    try:
        result = mongo.coll.update_one(
            {"_id": oid},
            {"$set": update_fields},
        )
        print(f"[*] modified_count={result.modified_count}")
    except Exception as e:
        print("[✗] update failed")
        print(str(e))
        raise HTTPException(status_code=500, detail={"updated": False})

    return {"updated": result.modified_count > 0}


@router.get("/get_incident")
async def get_incident(id: str = Query(None), mongo=Depends(get_mongo)):
    print(f"[*] get_incident called id={id}")

    if not id:
        print("[✗] missing id")
        raise HTTPException(status_code=400, detail="id is required")

    try:
        oid = ObjectId(id)
    except Exception:
        print("[✗] invalid ObjectId")
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    try:
        doc = mongo.coll.find_one({"_id": oid})
        if not doc:
            print("[✗] incident not found")
            raise HTTPException(status_code=404, detail="Incident not found")

        print("[✓] incident found")
        return JSONResponse(content=json.loads(dumps(doc)))
    except HTTPException:
        raise
    except Exception as e:
        print("[✗] get_incident failed")
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/livez")
async def livez():
    return "OK"


@router.get("/readyz")
async def readyz():
    try:
        _ = get_mongo()
        return {"ready": True}
    except Exception:
        return JSONResponse(content={"ready": False}, status_code=503)
