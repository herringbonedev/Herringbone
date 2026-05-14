import os
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger

from app.config import ALLOWED_COLLECTIONS, MAX_LIMIT, MAX_SCHEMA_SAMPLE
from app.service import search_collection_service, get_collection_schema


search_read = require_scopes("search:query")

router = APIRouter(
    prefix="/herringbone/search",
    tags=["search"],
)

audit = AuditLogger()


class SearchParams(BaseModel):
    q: Optional[str] = None
    after: Optional[str] = None
    from_ts: Optional[str] = None
    to_ts: Optional[str] = None
    limit: int = 100
    sort: Optional[str] = None
    order: Literal["asc", "desc"] = "desc"
    severity_min: Optional[int] = None
    severity_max: Optional[int] = None
    filter_field: Optional[str] = None
    filter_kind: Optional[str] = None
    filter_min: Optional[int] = None
    filter_max: Optional[int] = None
    filter_in: Optional[str] = None
    filter_value: Optional[str] = None


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


def assert_allowed_collection(collection: str):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown collection: {collection}")


def get_params(
    q: Optional[str] = Query(None),
    after: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=MAX_LIMIT),
    sort: Optional[str] = Query(None),
    order: Literal["asc", "desc"] = Query("desc"),
    severity_min: Optional[int] = Query(None),
    severity_max: Optional[int] = Query(None),
    filter_field: Optional[str] = Query(None),
    filter_kind: Optional[str] = Query(None),
    filter_min: Optional[int] = Query(None),
    filter_max: Optional[int] = Query(None),
    filter_in: Optional[str] = Query(None),
    filter_value: Optional[str] = Query(None),
):
    return SearchParams(
        q=q,
        after=after,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        sort=sort,
        order=order,
        severity_min=severity_min,
        severity_max=severity_max,
        filter_field=filter_field,
        filter_kind=filter_kind,
        filter_min=filter_min,
        filter_max=filter_max,
        filter_in=filter_in,
        filter_value=filter_value,
    )




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

@router.get("/{collection}/schema")
async def collection_schema(
    collection: str,
    request: Request,
    mongo=Depends(get_mongo),
    identity=Depends(search_read),
):
    assert_allowed_collection(collection)

    context_id = request.state.context_id

    try:
        fields = get_collection_schema(
            mongo=mongo,
            collection=collection,
            context_id=context_id,
            sample_size=MAX_SCHEMA_SAMPLE,
        )

        audit.log(
            event="search_schema",
            identity=identity,
            request=request,
            metadata={
                "collection": collection,
                "field_count": len(fields),
                "context_id": context_id,
            },
        )

        return {
            "collection": collection,
            "fields": fields,
        }

    except Exception as e:
        audit.log(
            event="search_schema_failed",
            identity=identity,
            request=request,
            result="failure",
            severity="ERROR",
            metadata={
                "collection": collection,
                "context_id": context_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{collection}")
async def search_collection(
    collection: str,
    request: Request,
    params: SearchParams = Depends(get_params),
    mongo=Depends(get_mongo),
    identity=Depends(search_read),
):
    assert_allowed_collection(collection)

    context_id = request.state.context_id

    try:
        results, next_after = search_collection_service(
            mongo=mongo,
            collection=collection,
            params=params,
            context_id=context_id,
        )

        audit.log(
            event="search_collection",
            identity=identity,
            request=request,
            metadata={
                "collection": collection,
                "query": params.q,
                "count": len(results),
                "context_id": context_id,
                "next_after": next_after,
            },
        )

        return JSONResponse(
            content={
                "collection": collection,
                "count": len(results),
                "results": results,
                "next_after": next_after,
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        audit.log(
            event="search_collection_failed",
            identity=identity,
            request=request,
            result="failure",
            severity="ERROR",
            metadata={
                "collection": collection,
                "context_id": context_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail=str(e))
