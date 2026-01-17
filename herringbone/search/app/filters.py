from datetime import datetime
from fastapi import HTTPException
from typing import Optional, Dict, Any, List


def parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(400, f"Invalid timestamp: {ts}")


def default_time_field(collection: str) -> str:
    return {
        "events": "ingested_at",
        "parse_results": "parsed_at",
        "event_state": "last_updated",
        "incidents": "created_at",
        "detections": "inserted_at",
        "parse_results": "created_at",
    }.get(collection, "inserted_at")


def _split_csv(v: Optional[str]) -> List[str]:
    if not v:
        return []
    parts = [x.strip() for x in v.split(",")]
    return [x for x in parts if x]


def build_range_filters(
    collection: str,
    filter_query: Dict[str, Any],
    severity_min: Optional[int],
    severity_max: Optional[int],
    from_ts: Optional[str],
    to_ts: Optional[str],
    filter_field: Optional[str] = None,
    filter_kind: Optional[str] = None,
    filter_min: Optional[int] = None,
    filter_max: Optional[int] = None,
    filter_in: Optional[str] = None,
) -> Dict[str, Any]:
    
    # generic field filter
    if filter_field:
        if filter_kind == "range":
            r: Dict[str, Any] = {}
            if filter_min is not None:
                r["$gte"] = filter_min
            if filter_max is not None:
                r["$lte"] = filter_max
            if r:
                filter_query[filter_field] = r

        elif filter_kind == "in":
            values = _split_csv(filter_in)
            if values:
                filter_query[filter_field] = {"$in": values}

        elif filter_kind is not None:
            raise HTTPException(400, "filter_kind must be 'range' or 'in'")

    # time range
    if from_ts or to_ts:
        field = default_time_field(collection)
        r: Dict[str, Any] = {}
        if from_ts:
            r["$gte"] = parse_iso(from_ts)
        if to_ts:
            r["$lte"] = parse_iso(to_ts)
        filter_query[field] = r

    return filter_query
