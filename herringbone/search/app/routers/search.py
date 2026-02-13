from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId
import os

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.user import get_current_user
from app.service import search_collection_service, get_collection_fields

from config import (
    MAX_LIMIT,
    MAX_SCHEMA_SAMPLE,
    MAX_SCHEMA_DEPTH,
    MAX_ENUM_VALUES,
    ALLOWED_COLLECTIONS,
    SORTABLE_FIELDS,
    ALLOWED_OPERATORS,
)

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
        from_ts: Optional[str],
        to_ts: Optional[str],
        sort: Optional[str],
        order: str,
        filter_field: Optional[str] = None,
        filter_kind: Optional[str] = None,
        filter_min: Optional[int] = None,
        filter_max: Optional[int] = None,
        filter_in: Optional[str] = None,
    ):
        self.limit = limit
        self.q = q
        self.after = after
        self.from_ts = from_ts
        self.to_ts = to_ts
        self.sort = sort
        self.order = order
        self.filter_field = filter_field
        self.filter_kind = filter_kind
        self.filter_min = filter_min
        self.filter_max = filter_max
        self.filter_in = filter_in
        self.severity_min = None
        self.severity_max = None


@router.get("/{collection}")
def search_collection(
    collection: str,
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
    q: Optional[str] = Query(None),
    after: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    filter_field: Optional[str] = Query(None),
    filter_kind: Optional[str] = Query(None, pattern="^(range|in)$"),
    filter_min: Optional[int] = Query(None),
    filter_max: Optional[int] = Query(None),
    filter_in: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    user=Depends(get_current_user),
):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Collection not allowed")

    params = SearchParams(
        limit=limit,
        q=q,
        after=after,
        from_ts=from_ts,
        to_ts=to_ts,
        sort=sort,
        order=order,
        filter_field=filter_field,
        filter_kind=filter_kind,
        filter_min=filter_min,
        filter_max=filter_max,
        filter_in=filter_in,
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
def list_collection_fields(
    collection: str,
    user=Depends(get_current_user),
):
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


def _infer_type(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int) or isinstance(v, float):
        return "number"
    if isinstance(v, datetime):
        return "datetime"
    if isinstance(v, ObjectId):
        return "objectid"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    if v is None:
        return "null"
    return "unknown"


def _normalize_example(v: Any):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, ObjectId):
        return str(v)
    return v


def _record_scalar(entry: Dict[str, Any], v: Any, t: str):
    ex = _normalize_example(v)

    if len(entry["examples"]) < 3:
        entry["examples"].append(ex)

    if t == "string" and len(entry["enum"]) < MAX_ENUM_VALUES:
        entry["enum"].add(v)


def _walk_fields(obj: Any, prefix: str, depth: int, out: Dict[str, Dict[str, Any]]):
    if depth > MAX_SCHEMA_DEPTH:
        return

    if isinstance(obj, list):
        for item in obj[:5]:
            _walk_fields(item, prefix, depth + 1, out)
        return

    if not isinstance(obj, dict):
        return

    for k, v in obj.items():
        if not isinstance(k, str):
            continue

        path = f"{prefix}.{k}" if prefix else k
        t = _infer_type(v)

        entry = out.setdefault(path, {
            "path": path,
            "types": set(),
            "examples": [],
            "enum": set(),
        })

        entry["types"].add(t)

        if t in ("string", "number", "bool", "datetime", "objectid"):
            if v is not None:
                _record_scalar(entry, v, t)

        elif t == "array":
            for item in v[:5]:
                it = _infer_type(item)

                entry["types"].add(it)

                if it in ("string", "number", "bool", "datetime", "objectid"):
                    _record_scalar(entry, item, it)

                elif isinstance(item, dict):
                    _walk_fields(item, path, depth + 1, out)

        elif isinstance(v, dict):
            _walk_fields(v, path, depth + 1, out)


@router.get("/{collection}/schema")
def get_collection_schema(
    collection: str,
    user=Depends(get_current_user),
):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Collection not allowed")

    mongo = get_mongo()

    try:
        docs = mongo.find_sorted(
            collection=collection,
            filter_query={},
            sort=[("_id", -1)],
            limit=MAX_SCHEMA_SAMPLE,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    out: Dict[str, Dict[str, Any]] = {}

    for d in docs or []:
        _walk_fields(d, "", 0, out)

    fields: List[Dict[str, Any]] = []
    for meta in out.values():
        fields.append({
            "path": meta["path"],
            "types": sorted(list(meta["types"])),
            "examples": meta["examples"],
            "enum": sorted(list(meta["enum"])),
        })

    fields.sort(key=lambda x: x["path"])

    return {
        "collection": collection,
        "count": len(fields),
        "fields": fields,
    }
