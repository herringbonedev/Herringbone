from datetime import datetime
from fastapi import HTTPException
from typing import Optional, Dict, Any, List
from bson import ObjectId
import re

from app.config import COLLECTION_TIME_FIELDS, DATE_FIELD_NAMES, BLOCKED_QUERY_FIELDS, MAX_IN_VALUES, MAX_REGEX_LENGTH


def parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(400, f"Invalid timestamp: {ts}")


def default_time_field(collection: str) -> str:
    return COLLECTION_TIME_FIELDS.get(collection, ("created_at",))[0]


def time_fields(collection: str) -> List[str]:
    return list(COLLECTION_TIME_FIELDS.get(collection, ("created_at",)))


def _split_csv(v: Optional[str]) -> List[str]:
    if not v:
        return []
    parts = [x.strip() for x in v.split(",")]
    return [x for x in parts if x]


def _looks_date_field(field: str) -> bool:
    leaf = field.split(".")[-1]
    return field in DATE_FIELD_NAMES or leaf in DATE_FIELD_NAMES or leaf.endswith("_at") or leaf.endswith("_time")


def _cast_value(field: str, value: str) -> Any:
    """
    Field-aware casting. Important: do not blindly cast 24-char event_id values to ObjectId.
    Only _id should be cast to ObjectId.
    """
    if value is None:
        return value

    if field == "_id" and ObjectId.is_valid(value):
        return ObjectId(value)

    if _looks_date_field(field):
        return parse_iso(value)

    try:
        return int(value)
    except Exception:
        pass

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    return value


def merge_condition(filter_query: Dict[str, Any], condition: Dict[str, Any]) -> Dict[str, Any]:
    if not condition:
        return filter_query
    if not filter_query:
        filter_query.update(condition)
        return filter_query
    if "$and" in filter_query and len(filter_query) == 1 and isinstance(filter_query["$and"], list):
        filter_query["$and"].append(condition)
        return filter_query
    existing = dict(filter_query)
    filter_query.clear()
    filter_query["$and"] = [existing, condition]
    return filter_query


def build_time_condition(collection: str, from_ts: Optional[str], to_ts: Optional[str]) -> Dict[str, Any]:
    if not (from_ts or to_ts):
        return {}

    r: Dict[str, Any] = {}
    if from_ts:
        r["$gte"] = parse_iso(from_ts)
    if to_ts:
        r["$lte"] = parse_iso(to_ts)

    fields = time_fields(collection)
    if len(fields) == 1:
        return {fields[0]: r}
    return {"$or": [{field: dict(r)} for field in fields]}


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
    filter_value: Optional[str] = None,
) -> Dict[str, Any]:

    if severity_min is not None or severity_max is not None:
        severity_range: Dict[str, Any] = {}
        if severity_min is not None:
            severity_range["$gte"] = severity_min
        if severity_max is not None:
            severity_range["$lte"] = severity_max
        merge_condition(filter_query, {"severity": severity_range})

    if filter_field:
        if filter_field in BLOCKED_QUERY_FIELDS:
            raise HTTPException(400, f"Field is enforced by the server and cannot be filtered directly: {filter_field}")

        condition: Dict[str, Any] = {}

        if filter_kind == "range":
            r: Dict[str, Any] = {}
            if filter_min is not None:
                r["$gte"] = filter_min
            if filter_max is not None:
                r["$lte"] = filter_max
            if r:
                condition = {filter_field: r}

        elif filter_kind == "in":
            values = _split_csv(filter_in)
            if len(values) > MAX_IN_VALUES:
                raise HTTPException(400, "filter_in has too many values")
            if values:
                condition = {filter_field: {"$in": [_cast_value(filter_field, v) for v in values]}}

        elif filter_kind == "eq":
            if filter_value is not None:
                condition = {filter_field: _cast_value(filter_field, filter_value)}

        elif filter_kind == "contains":
            if filter_value:
                if len(filter_value) > MAX_REGEX_LENGTH:
                    raise HTTPException(400, "filter_value is too long")
                safe_value = re.escape(filter_value)
                condition = {filter_field: {"$regex": safe_value, "$options": "i"}}

        elif filter_kind == "prefix":
            if filter_value:
                if len(filter_value) > MAX_REGEX_LENGTH:
                    raise HTTPException(400, "filter_value is too long")
                safe_value = re.escape(filter_value)
                condition = {filter_field: {"$regex": f"^{safe_value}", "$options": "i"}}

        elif filter_kind is not None:
            raise HTTPException(400, "filter_kind must be one of: range, in, eq, contains, prefix")

        merge_condition(filter_query, condition)

    merge_condition(filter_query, build_time_condition(collection, from_ts, to_ts))

    return filter_query
