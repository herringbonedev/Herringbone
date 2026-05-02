from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from bson import ObjectId
from bson.json_util import dumps

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes, require_internal_scopes, get_context
from modules.audit.logger import AuditLogger

from app.schema import IncidentSchema

import os
import json


incident_writer = require_scopes("incidents:write")
incident_reader = require_scopes("incidents:read")
internal_incident_writer = require_internal_scopes("incidents:write")


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


def resolve_internal_context(
    payload: dict,
    request: Request,
    identity: dict,
) -> str:
    payload_context_id = payload.get("context_id")

    header_context_id = (
        request.headers.get("X-Herringbone-Context")
        or request.headers.get("X-Herringbone-Org")
    )

    context_id = payload_context_id or header_context_id

    if not context_id:
        audit.log(
            event="incidentset_missing_context",
            identity=identity,
            request=request,
            result="failure",
            severity="WARNING",
        )
        raise HTTPException(status_code=400, detail="Missing context_id")

    if (
        payload_context_id
        and header_context_id
        and str(payload_context_id) != str(header_context_id)
    ):
        audit.log(
            event="incidentset_context_mismatch",
            identity=identity,
            request=request,
            result="failure",
            severity="WARNING",
            metadata={
                "payload_context_id": str(payload_context_id),
                "header_context_id": str(header_context_id),
            },
        )
        raise HTTPException(status_code=403, detail="Context mismatch")

    context_id = str(context_id)

    request.state.context_id = context_id
    request.state.identity = identity

    return context_id


def normalize_object_id(raw_id):
    if isinstance(raw_id, dict):
        raw_id = raw_id.get("$oid")

    if not raw_id:
        return None

    return str(raw_id)


def build_update_doc(payload: dict):
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

    return update_doc


def prepare_incident_create(data: dict) -> dict:
    now = datetime.now(timezone.utc)

    data.pop("context_id", None)

    data["created_at"] = now
    data["last_updated"] = now
    data["state"] = {"last_updated": now}
    data["status"] = data.get("status", "open")

    return data


async def insert_incident_common(
    data: dict,
    request: Request,
    mongo,
    identity: dict,
    context_id: str,
    caller_type: str,
):
    data = prepare_incident_create(data)

    validation = validator(data)

    if not validation["valid"]:
        audit.log(
            event="incident_insert_validation_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={
                "context_id": context_id,
                "caller_type": caller_type,
                "validation": validation,
            },
        )

        raise HTTPException(status_code=400, detail=validation)

    try:
        mongo.insert_one(
            incidents_collection(),
            data,
            context_id=context_id,
        )

        audit.log(
            event="incident_inserted",
            identity=identity,
            request=request,
            target=data.get("title"),
            metadata={
                "status": data["status"],
                "context_id": context_id,
                "caller_type": caller_type,
            },
        )

    except Exception as e:
        audit.log(
            event="incident_insert_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={
                "context_id": context_id,
                "caller_type": caller_type,
                "error": str(e),
            },
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))

    return {"inserted": True}


async def update_incident_common(
    payload: dict,
    request: Request,
    mongo,
    identity: dict,
    context_id: str,
    caller_type: str,
):
    raw_id = payload.pop("_id", None)
    payload.pop("context_id", None)

    raw_id = normalize_object_id(raw_id)

    if not raw_id:
        audit.log(
            event="incident_update_missing_id",
            identity=identity,
            request=request,
            result="failure",
            metadata={
                "context_id": context_id,
                "caller_type": caller_type,
            },
        )

        raise HTTPException(status_code=400, detail="Missing _id")

    try:
        oid = ObjectId(raw_id)
    except Exception:
        audit.log(
            event="incident_update_invalid_id",
            identity=identity,
            request=request,
            target=str(raw_id),
            result="failure",
            metadata={
                "context_id": context_id,
                "caller_type": caller_type,
            },
        )

        raise HTTPException(status_code=400, detail="Invalid _id")

    update_doc = build_update_doc(payload)

    try:
        mongo.update_one(
            incidents_collection(),
            {"_id": oid},
            update_doc,
            context_id=context_id,
        )

        audit.log(
            event="incident_updated",
            identity=identity,
            request=request,
            target=str(oid),
            metadata={
                "context_id": context_id,
                "caller_type": caller_type,
            },
        )

    except Exception as e:
        audit.log(
            event="incident_update_failed",
            identity=identity,
            request=request,
            target=str(oid),
            result="failure",
            metadata={
                "context_id": context_id,
                "caller_type": caller_type,
                "error": str(e),
            },
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))

    return {"updated": True}


@router.post("/insert_incident", dependencies=[Depends(get_context)])
async def insert_incident(
    payload: IncidentCreate,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_writer),
):
    context_id = request.state.context_id
    data = payload.model_dump()

    return await insert_incident_common(
        data=data,
        request=request,
        mongo=mongo,
        identity=identity,
        context_id=context_id,
        caller_type="user",
    )


@router.post("/update_incident", dependencies=[Depends(get_context)])
async def update_incident(
    payload: dict,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_writer),
):
    context_id = request.state.context_id

    return await update_incident_common(
        payload=payload,
        request=request,
        mongo=mongo,
        identity=identity,
        context_id=context_id,
        caller_type="user",
    )


@router.post("/internal/insert_incident")
async def internal_insert_incident(
    payload: IncidentCreate,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(internal_incident_writer),
):
    data = payload.model_dump()
    context_id = resolve_internal_context(data, request, identity)

    return await insert_incident_common(
        data=data,
        request=request,
        mongo=mongo,
        identity=identity,
        context_id=context_id,
        caller_type="internal",
    )


@router.post("/internal/update_incident")
async def internal_update_incident(
    payload: dict,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(internal_incident_writer),
):
    context_id = resolve_internal_context(payload, request, identity)

    return await update_incident_common(
        payload=payload,
        request=request,
        mongo=mongo,
        identity=identity,
        context_id=context_id,
        caller_type="internal",
    )


@router.get("/get_incidents", dependencies=[Depends(get_context)])
async def get_incidents(
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_reader),
):
    context_id = request.state.context_id

    try:
        docs = mongo.find_with_context(
            incidents_collection(),
            {},
            context_id=context_id,
        )

        audit.log(
            event="incident_list_accessed",
            identity=identity,
            request=request,
            metadata={"context_id": context_id},
        )

        return JSONResponse(content=json.loads(dumps(docs)))

    except Exception as e:
        audit.log(
            event="incident_list_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={
                "context_id": context_id,
                "error": str(e),
            },
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_incident/{incident_id}", dependencies=[Depends(get_context)])
async def get_incident(
    incident_id: str,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(incident_reader),
):
    context_id = request.state.context_id

    try:
        oid = ObjectId(incident_id)
    except Exception:
        audit.log(
            event="incident_lookup_invalid_id",
            identity=identity,
            request=request,
            target=incident_id,
            result="failure",
            metadata={"context_id": context_id},
        )

        raise HTTPException(status_code=400, detail="Invalid incident id")

    try:
        doc = mongo.find_one_with_context(
            incidents_collection(),
            {"_id": oid},
            context_id=context_id,
        )
    except Exception as e:
        audit.log(
            event="incident_lookup_failed",
            identity=identity,
            request=request,
            target=incident_id,
            result="failure",
            metadata={
                "context_id": context_id,
                "error": str(e),
            },
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
            metadata={"context_id": context_id},
        )

        raise HTTPException(status_code=404, detail="Incident not found")

    audit.log(
        event="incident_lookup_success",
        identity=identity,
        request=request,
        target=incident_id,
        metadata={"context_id": context_id},
    )

    return JSONResponse(content=json.loads(dumps(doc)))


@router.get("/livez")
async def livez():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(mongo=Depends(get_mongo)):
    try:
        mongo.find_one(incidents_collection(), {})
        return {"ready": True}
    except Exception:
        return JSONResponse(content={"ready": False}, status_code=503)