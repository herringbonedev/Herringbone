from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import os

from modules.database.mongo_db import HerringboneMongoDatabase
from service import search_collection_service, get_collection_fields
from config import ALLOWED_COLLECTIONS, MAX_LIMIT

router = APIRouter(prefix="/herringbone/search", tags=["search"])


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


class SearchParams:
    def __init__(
        self,
        limit: int,
        q: Optional[str],
        after: Optional[str],
        severity_min: Optional[int],
        severity_max: Optional[int],
        from_ts: Optional[str],
        to_ts: Optional[str],
        sort: Optional[str],
        order: str,
    ):
        self.limit = limit
        self.q = q
        self.after = after
        self.severity_min = severity_min
        self.severity_max = severity_max
        self.from_ts = from_ts
        self.to_ts = to_ts
        self.sort = sort
        self.order = order


@router.get("/{collection}")
def search_collection(
    collection: str,
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
    q: Optional[str] = Query(None, description='JSON string, e.g. {"severity":{"$gte":80}}'),
    after: Optional[str] = Query(None, description="Cursor ObjectId string"),
    severity_min: Optional[int] = Query(None, ge=0, le=100),
    severity_max: Optional[int] = Query(None, ge=0, le=100),
    from_ts: Optional[str] = Query(None, description="ISO timestamp"),
    to_ts: Optional[str] = Query(None, description="ISO timestamp"),
    sort: Optional[str] = Query(None),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Collection not allowed")

    params = SearchParams(
        limit=limit,
        q=q,
        after=after,
        severity_min=severity_min,
        severity_max=severity_max,
        from_ts=from_ts,
        to_ts=to_ts,
        sort=sort,
        order=order,
    )

    mongo = get_mongo()

    try:
        results, next_after = search_collection_service(
            mongo=mongo,
            collection=collection,
            params=params,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "collection": collection,
        "limit": limit,
        "count": len(results),
        "after": after,
        "next_after": next_after,
        "results": results,
    }


@router.get("/{collection}/fields")
def list_collection_fields(collection: str):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Collection not allowed")

    mongo = get_mongo()

    try:
        fields = get_collection_fields(mongo, collection)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "collection": collection,
        "count": len(fields),
        "fields": fields,
    }
