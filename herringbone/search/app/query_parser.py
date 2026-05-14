import json
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from fastapi import HTTPException
from app.config import DATE_FIELD_NAMES
from app.validators import validate_query_obj


def _parse_iso(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return value


def _cast_field_value(field: str, value: Any) -> Any:
    if value is None:
        return value

    leaf = field.split(".")[-1]

    if field == "_id" and isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)

    if (field in DATE_FIELD_NAMES or leaf in DATE_FIELD_NAMES or leaf.endswith("_at") or leaf.endswith("_time")) and isinstance(value, str):
        return _parse_iso(value)

    return value


def _normalize_field_expr(field: str, expr: Any) -> Any:
    if isinstance(expr, dict):
        normalized = {}
        for op, value in expr.items():
            if op in {"$in", "$nin"} and isinstance(value, list):
                normalized[op] = [_cast_field_value(field, item) for item in value]
            elif op in {"$eq", "$ne", "$gte", "$lte", "$gt", "$lt"}:
                normalized[op] = _cast_field_value(field, value)
            else:
                normalized[op] = normalize_query_obj(value)
        return normalized

    return _cast_field_value(field, expr)


def normalize_query_obj(obj: Any) -> Any:
    if isinstance(obj, list):
        return [normalize_query_obj(item) for item in obj]

    if not isinstance(obj, dict):
        return obj

    normalized: Dict[str, Any] = {}
    for key, value in obj.items():
        if key in {"$and", "$or"}:
            normalized[key] = [normalize_query_obj(item) for item in value]
        elif key.startswith("$"):
            normalized[key] = normalize_query_obj(value)
        else:
            normalized[key] = _normalize_field_expr(key, value)
    return normalized


def parse_q_string(q: Optional[str]) -> Dict[str, Any]:
    if not q:
        return {}

    try:
        obj = json.loads(q)
    except Exception:
        raise HTTPException(400, "query must be valid JSON")

    if not isinstance(obj, dict):
        raise HTTPException(400, "query must be a JSON object")

    if len(obj) > 50:
        raise HTTPException(400, "Too many query fields")

    validate_query_obj(obj)
    return normalize_query_obj(obj)
