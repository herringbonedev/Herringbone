from bson import ObjectId
from fastapi import HTTPException
from typing import Optional, Dict, Any


def coerce_after(after: Optional[str]) -> Optional[ObjectId]:
    if not after:
        return None
    try:
        return ObjectId(after)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid after cursor (must be ObjectId string)")


def apply_after(filter_query: Dict[str, Any], after_oid: Optional[ObjectId], order: str = "desc") -> Dict[str, Any]:
    if not after_oid:
        return filter_query

    if "_id" in filter_query:
        raise HTTPException(status_code=400, detail="Do not include _id in query when using after")

    op = "$gt" if order == "asc" else "$lt"
    cursor_condition = {"_id": {op: after_oid}}

    if not filter_query:
        filter_query.update(cursor_condition)
        return filter_query

    if "$and" in filter_query and len(filter_query) == 1 and isinstance(filter_query["$and"], list):
        filter_query["$and"].append(cursor_condition)
        return filter_query

    existing = dict(filter_query)
    filter_query.clear()
    filter_query["$and"] = [existing, cursor_condition]
    return filter_query
