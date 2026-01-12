from datetime import datetime
from fastapi import HTTPException
from typing import Optional, Dict, Any

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
    }.get(collection, "inserted_at")

def build_range_filters(collection, filter_query, severity_min, severity_max, from_ts, to_ts):
    if severity_min is not None or severity_max is not None:
        r = {}
        if severity_min is not None:
            r["$gte"] = severity_min
        if severity_max is not None:
            r["$lte"] = severity_max
        filter_query["severity"] = r

    if from_ts or to_ts:
        field = default_time_field(collection)
        r = {}
        if from_ts:
            r["$gte"] = parse_iso(from_ts)
        if to_ts:
            r["$lte"] = parse_iso(to_ts)
        filter_query[field] = r

    return filter_query
