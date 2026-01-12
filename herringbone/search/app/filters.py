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


def build_range_filters(
    collection: str,
    filter_query: Dict[str, Any],
    severity_min: Optional[int],
    severity_max: Optional[int],
    from_ts: Optional[str],
    to_ts: Optional[str],
) -> Dict[str, Any]:
    
    if severity_min is not None or severity_max is not None:

        if collection == "incidents":
            priorities = []

            if severity_min is not None or severity_max is not None:
                lo = severity_min if severity_min is not None else 0
                hi = severity_max if severity_max is not None else 100

                if lo <= 39 and hi >= 1:
                    priorities.append("low")
                if lo <= 69 and hi >= 40:
                    priorities.append("medium")
                if lo <= 89 and hi >= 70:
                    priorities.append("high")
                if lo <= 100 and hi >= 90:
                    priorities.append("critical")

            if priorities:
                filter_query["priority"] = {"$in": priorities}

        else:
            r: Dict[str, Any] = {}

            if severity_min is not None:
                r["$gte"] = severity_min
            if severity_max is not None:
                r["$lte"] = severity_max

            filter_query["severity"] = r
    
    if from_ts or to_ts:
        field = default_time_field(collection)
        r: Dict[str, Any] = {}

        if from_ts:
            r["$gte"] = parse_iso(from_ts)
        if to_ts:
            r["$lte"] = parse_iso(to_ts)

        filter_query[field] = r

    return filter_query

