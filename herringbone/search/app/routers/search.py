from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from bson.json_util import dumps
from datetime import datetime, timedelta, UTC
import os
import json

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger


search_read = require_scopes("search:query")

router = APIRouter(
    prefix="/herringbone/search",
    tags=["search"],
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


def parse_ts(value: str | None):
    if not value:
        return None

    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp: {value}")


def parse_json_query(q: str | None) -> dict:
    if not q:
        return {}

    try:
        parsed = json.loads(q)
    except Exception:
        return {
            "$or": [
                {"raw": {"$regex": q, "$options": "i"}},
                {"source.address": {"$regex": q, "$options": "i"}},
            ]
        }

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="q must be a JSON object or search string")

    return parsed


def apply_time_range(
    query: dict,
    field: str,
    from_ts: str | None,
    to_ts: str | None,
):
    start = parse_ts(from_ts)
    end = parse_ts(to_ts)

    if not start and not end:
        return query

    time_filter = {}

    if start:
        time_filter["$gte"] = start

    if end:
        time_filter["$lte"] = end

    query[field] = time_filter

    return query


@router.get("/events")
async def search_events(
    request: Request,
    q: str | None = Query(None),
    since_hours: int | None = Query(None),
    from_ts: str | None = Query(None),
    to_ts: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    mongo=Depends(get_mongo),
    identity=Depends(search_read),
):
    context_id = request.state.context_id

    query = parse_json_query(q)

    if since_hours:
        since = datetime.now(UTC) - timedelta(hours=since_hours)
        query["ingested_at"] = {"$gte": since}

    query = apply_time_range(
        query=query,
        field="ingested_at",
        from_ts=from_ts,
        to_ts=to_ts,
    )

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
    q: str | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    from_ts: str | None = Query(None),
    to_ts: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    mongo=Depends(get_mongo),
    identity=Depends(search_read),
):
    context_id = request.state.context_id

    query = parse_json_query(q)

    if status:
        query["status"] = status

    if priority:
        query["priority"] = priority

    query = apply_time_range(
        query=query,
        field="created_at",
        from_ts=from_ts,
        to_ts=to_ts,
    )

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
                "query": q,
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
    q: str | None = Query(None),
    severity_min: int | None = Query(None),
    from_ts: str | None = Query(None),
    to_ts: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    mongo=Depends(get_mongo),
    identity=Depends(search_read),
):
    context_id = request.state.context_id

    query = parse_json_query(q)

    if severity_min is not None:
        query["severity"] = {"$gte": severity_min}

    query = apply_time_range(
        query=query,
        field="inserted_at",
        from_ts=from_ts,
        to_ts=to_ts,
    )

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
                "query": q,
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