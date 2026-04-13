from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.json_util import dumps
from datetime import datetime, timedelta, UTC
import os
import json

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes, get_context
from modules.audit.logger import AuditLogger


search_read = require_scopes("search:query")

router = APIRouter(
    prefix="/herringbone/search",
    tags=["search"],
    dependencies=[Depends(get_context)],
)

audit = AuditLogger()


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
    )


def encode(obj):
    return json.loads(dumps(obj))


@router.get("/events")
async def search_events(
    request: Request,
    q: str | None = Query(None),
    since_hours: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    mongo=Depends(get_mongo),
    context=Depends(search_read),
):

    context_id = request.state.context_id
    identity = context["identity"]

    query = {}
    
    if q:
        query["$or"] = [
            {"raw": {"$regex": q, "$options": "i"}},
            {"source.address": {"$regex": q, "$options": "i"}},
        ]
    
    if since_hours:
        since = datetime.now(UTC) - timedelta(hours=since_hours)
        query["ingested_at"] = {"$gte": since}

    try:

        results = mongo.find_sorted_with_context(
            collection="events",
            filter_query=query,
            context_id=context_id,
            sort=[("_id", -1)],
            limit=limit,
        )

        audit.log(
            event="search_events",
            identity=identity,
            request=request,
            metadata={
                "query": q,
                "count": len(results),
                "context_id": context_id,
            },
        )

        return JSONResponse(content=encode(results))

    except Exception as e:

        audit.log(
            event="search_events_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e), "context_id": context_id},
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents")
async def search_incidents(
    request: Request,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    mongo=Depends(get_mongo),
    context=Depends(search_read),
):

    context_id = request.state.context_id
    identity = context["identity"]

    query = {}

    if status:
        query["status"] = status

    if priority:
        query["priority"] = priority

    try:

        results = mongo.find_sorted_with_context(
            collection="incidents",
            filter_query=query,
            context_id=context_id,
            sort=[("created_at", -1)],
            limit=limit,
        )

        audit.log(
            event="search_incidents",
            identity=identity,
            request=request,
            metadata={
                "status": status,
                "priority": priority,
                "count": len(results),
                "context_id": context_id,
            },
        )

        return JSONResponse(content=encode(results))

    except Exception as e:

        audit.log(
            event="search_incidents_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e), "context_id": context_id},
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detections")
async def search_detections(
    request: Request,
    severity_min: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    mongo=Depends(get_mongo),
    context=Depends(search_read),
):

    context_id = request.state.context_id
    identity = context["identity"]

    query = {}

    if severity_min is not None:
        query["severity"] = {"$gte": severity_min}

    try:

        results = mongo.find_sorted_with_context(
            collection="detections",
            filter_query=query,
            context_id=context_id,
            sort=[("inserted_at", -1)],
            limit=limit,
        )

        audit.log(
            event="search_detections",
            identity=identity,
            request=request,
            metadata={
                "severity_min": severity_min,
                "count": len(results),
                "context_id": context_id,
            },
        )

        return JSONResponse(content=encode(results))

    except Exception as e:

        audit.log(
            event="search_detections_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e), "context_id": context_id},
            severity="ERROR",
        )

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/livez")
async def livez():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(mongo=Depends(get_mongo)):
    try:
        mongo.find_one("events", {})
        return {"ready": True}
    except Exception:
        return JSONResponse(content={"ready": False}, status_code=503)