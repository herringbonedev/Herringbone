from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
from bson.json_util import dumps
import os
import json

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger

from app.schema import RuleSchema


ruleset_write = require_scopes("rules:write")
ruleset_read = require_scopes("rules:read")
ruleset_admin = require_scopes("rules:admin")

router = APIRouter(
    prefix="/detectionengine/ruleset",
    tags=["ruleset"],
)

validator = RuleSchema()
audit = AuditLogger()


class RuleBase(BaseModel):
    model_config = ConfigDict(extra="allow")


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
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(ruleset_write),
):

    data = payload.model_dump()

    validation = validator(data)

    if not validation["valid"]:

        audit.log(
            event="rule_insert_validation_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata=validation,
        )

        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON", "details": validation["error"]},
        )

    try:

        mongo.insert_one("rules", data)

        audit.log(
            event="rule_inserted",
            identity=identity,
            request=request,
            metadata={"rule_name": data.get("name")},
        )

    except Exception as e:

        audit.log(
            event="rule_insert_failed",
            identity=identity,
            request=request,
            result="failure",
            severity="ERROR",
            metadata={"error": str(e)},
        )

        raise HTTPException(status_code=500, detail=str(e))

    return {"inserted": True}


@router.get("/get_rules")
async def get_rules(
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(ruleset_read),
):

    try:

        docs = mongo.find("rules", {})

        audit.log(
            event="rules_list_accessed",
            identity=identity,
            request=request,
            metadata={"count": len(docs)},
        )

        return JSONResponse(content=json.loads(dumps(docs)))

    except Exception as e:

        audit.log(
            event="rules_list_failed",
            identity=identity,
            request=request,
            result="failure",
            severity="ERROR",
            metadata={"error": str(e)},
        )

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/delete_rule")
async def delete_rule(
    id: str = Query(...),
    request: Request = None,
    mongo=Depends(get_mongo),
    identity=Depends(ruleset_admin),
):

    try:
        oid = ObjectId(id)
    except Exception:

        audit.log(
            event="rule_delete_invalid_id",
            identity=identity,
            request=request,
            target=id,
            result="failure",
        )

        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    try:

        mongo.delete_one("rules", {"_id": oid})

        audit.log(
            event="rule_deleted",
            identity=identity,
            request=request,
            target=str(oid),
        )

    except Exception as e:

        audit.log(
            event="rule_delete_failed",
            identity=identity,
            request=request,
            target=str(oid),
            result="failure",
            severity="ERROR",
            metadata={"error": str(e)},
        )

        raise HTTPException(status_code=500, detail=str(e))

    return {"deleted": True}


@router.post("/update_rule")
async def update_rule(
    payload: RuleUpdate,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(ruleset_write),
):

    data = payload.model_dump(by_alias=True)

    rule_id = data.pop("_id", None)

    if not rule_id:

        audit.log(
            event="rule_update_missing_id",
            identity=identity,
            request=request,
            result="failure",
        )

        raise HTTPException(status_code=400, detail="Missing rule _id")

    validation = validator(data)

    if not validation["valid"]:

        audit.log(
            event="rule_update_validation_failed",
            identity=identity,
            request=request,
            target=str(rule_id),
            result="failure",
            metadata=validation,
        )

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

        audit.log(
            event="rule_updated",
            identity=identity,
            request=request,
            target=str(oid),
        )

    except Exception as e:

        audit.log(
            event="rule_update_failed",
            identity=identity,
            request=request,
            target=str(oid),
            result="failure",
            severity="ERROR",
            metadata={"error": str(e)},
        )

        raise HTTPException(status_code=500, detail=str(e))

    return {"updated": True}


@router.get("/livez")
async def livez():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(mongo=Depends(get_mongo)):
    try:
        mongo.find_one("rules", {})
        return {"ready": True}
    except Exception:
        return JSONResponse(content={"ready": False}, status_code=503)