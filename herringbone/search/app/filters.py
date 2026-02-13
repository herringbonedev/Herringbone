
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
        "parse_results": "created_at",
        "event_state": "last_updated",
        "incidents": "created_at",
        "detections": "inserted_at",
    }.get(collection, "inserted_at")


def _split_csv(v: Optional[str]) -> List[str]:
    if not v:
        return []
    parts = [x.strip() for x in v.split(",")]
    return [x for x in parts if x]


def _build_single_filter(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    field = row.get("field")
    kind = row.get("kind")

    if not field or not kind:
        return None

    if kind == "range":
        r: Dict[str, Any] = {}
        if row.get("min") is not None:
            r["$gte"] = row["min"]
        if row.get("max") is not None:
            r["$lte"] = row["max"]
        if not r:
            return None
        return {field: r}

    if kind == "in":
        values = _split_csv(row.get("values"))
        if not values:
            return None
        return {field: {"$in": values}}

    raise HTTPException(400, "Invalid filter kind")


def build_range_filters(
    collection: str,
    base_query: Dict[str, Any],
    filters: Optional[List[Dict[str, Any]]] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:

    query_parts: List[Dict[str, Any]] = []

    # Preserve existing base query
    if base_query:
        query_parts.append(base_query)

    # Process filter rows
    if filters:
        current_and_group: List[Dict[str, Any]] = []
        or_groups: List[List[Dict[str, Any]]] = []

        for row in filters:
            mongo_filter = _build_single_filter(row)
            if not mongo_filter:
                continue

            join = row.get("join", "and")

            if join == "or":
                if current_and_group:
                    or_groups.append(current_and_group)
                    current_and_group = []
                current_and_group.append(mongo_filter)
            else:
                current_and_group.append(mongo_filter)

        if current_and_group:
            or_groups.append(current_and_group)

        if or_groups:
            if len(or_groups) == 1:
                query_parts.extend(or_groups[0])
            else:
                query_parts.append(
                    {
                        "$or": [
                            {"$and": group} if len(group) > 1 else group[0]
                            for group in or_groups
                        ]
                    }
                )

    # Time filtering
    if from_ts or to_ts:
        field = default_time_field(collection)
        r: Dict[str, Any] = {}

        if from_ts:
            r["$gte"] = parse_iso(from_ts)
        if to_ts:
            r["$lte"] = parse_iso(to_ts)

        query_parts.append({field: r})

    # Final query assembly
    if not query_parts:
        return {}

    if len(query_parts) == 1:
        return query_parts[0]

    return {"$and": query_parts}