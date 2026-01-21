from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from bson.json_util import dumps
from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.deps import get_current_user, require_admin
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
    db = HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        collection=os.environ.get("COLLECTION_NAME", "rules"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )
    db.open_mongo_connection()
    if db.coll is None:
        raise HTTPException(status_code=500, detail="Mongo connection not initialized")
    return db


@router.post("/insert_rule")
async def insert_rule(
    payload: RuleCreate,
    mongo=Depends(get_mongo),
    user=Depends(require_admin),
):
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


@router.get("/get_rules")
async def get_rules(
    mongo=Depends(get_mongo),
):
    try:
        docs = list(mongo.coll.find({}))
        return JSONResponse(content=json.loads(dumps(docs)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/delete_rule")
async def delete_rule(
    id: str = Query(None),
    mongo=Depends(get_mongo),
    user=Depends(require_admin),
):
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


@router.post("/update_rule")
async def update_rule(
    payload: RuleUpdate,
    mongo=Depends(get_mongo),
    user=Depends(require_admin),
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
        result = mongo.coll.update_one(
            {"_id": oid},
            {"$set": data},
        )
    except Exception:
        raise HTTPException(status_code=500, detail={"updated": False})

    return {"updated": result.modified_count > 0}


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
