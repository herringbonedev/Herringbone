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


def apply_after(filter_query: Dict[str, Any], after_oid: Optional[ObjectId]) -> Dict[str, Any]:
    if not after_oid:
        return filter_query

    if "_id" in filter_query:
        raise HTTPException(status_code=400, detail="Do not include _id in q when using after")
    
    filter_query["_id"] = {"$lt": after_oid}

    return filter_query

