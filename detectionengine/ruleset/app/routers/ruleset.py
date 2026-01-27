from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from bson.json_util import dumps
from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.service import require_service_scope
from modules.auth.mix import service_or_role
from schema import RuleSchema
import os
import json

router = APIRouter(
    prefix="/detectionengine/ruleset",
    tags=["ruleset"],
)

validator = RuleSchema()


class RuleBase(BaseModel):
    class Config:
        extra = "allow"


class RuleCreate(RuleBase):
    pass


class RuleUpdate(RuleBase):
    id: str = Field(..., alias="_id", serialization_alias="_id")


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
    )


@router.post("/insert_rule")
async def insert_rule(
    payload: RuleCreate,
    mongo=Depends(get_mongo),
    auth=Depends(service_or_role("rules:write", ["admin", "analyst"]))
):
    data = payload.dict()

    validation = validator(data)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON", "details": validation["error"]},
        )

    try:
        mongo.insert_one("rules", data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"inserted": True}


@router.get("/get_rules")
async def get_rules(
    mongo=Depends(get_mongo),
    auth=Depends(service_or_role("rules:read", ["admin", "analyst"]))
):
    try:
        docs = mongo.find("rules", {})
        return JSONResponse(content=json.loads(dumps(docs)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/delete_rule")
async def delete_rule(
    id: str = Query(...),
    mongo=Depends(get_mongo),
    auth=Depends(service_or_role("rules:write", ["admin"]))
):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    try:
        result = mongo.upsert_one("rules", {"_id": oid}, {}, clean_codec=False)
        deleted = mongo.find_one("rules", {"_id": oid}) is None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"deleted": deleted}


@router.post("/update_rule")
async def update_rule(
    payload: RuleUpdate,
    mongo=Depends(get_mongo),
        auth=Depends(service_or_role("rules:write", ["admin", "analyst"]))
):
    data = payload.model_dump(by_alias=True)

    rule_id = data.pop("_id", None)
    if not rule_id:
        raise HTTPException(status_code=400, detail="Missing rule _id")

    validation = validator(data)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON", "details": validation["error"]},
        )

    try:
        oid = ObjectId(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    try:
        mongo.upsert_one("rules", {"_id": oid}, data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"updated": True}


@router.get("/livez")
async def livez():
    return "OK"


@router.get("/readyz")
async def readyz(mongo=Depends(get_mongo)):
    try:
        mongo.find_one("rules", {})
        return {"ready": True}
    except Exception:
        return JSONResponse(content={"ready": False}, status_code=503)
