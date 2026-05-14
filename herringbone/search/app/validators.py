from typing import Any
from fastapi import HTTPException
from app.config import (
    ALLOWED_OPERATORS,
    BLOCKED_QUERY_FIELDS,
    MAX_IN_VALUES,
    MAX_REGEX_LENGTH,
)


def _is_plain_field_key(k: str) -> bool:
    if not isinstance(k, str) or not k:
        return False
    if k.startswith("$") or "$" in k or "\x00" in k:
        return False
    return True


def _validate_regex_options(v: Any) -> None:
    if not isinstance(v, str):
        raise HTTPException(400, "$options must be a string")
    if len(v) > 8 or any(ch not in "imsx" for ch in v):
        raise HTTPException(400, "$options may only contain i, m, s, or x")


def validate_query_obj(obj: Any, depth: int = 0) -> None:
    if depth > 12:
        raise HTTPException(400, "Query too deep")

    if isinstance(obj, list):
        if len(obj) > MAX_IN_VALUES:
            raise HTTPException(400, "Query list too large")
        for item in obj:
            validate_query_obj(item, depth + 1)
        return

    if not isinstance(obj, dict):
        return

    for k, v in obj.items():
        if k.startswith("$"):
            if k not in ALLOWED_OPERATORS:
                raise HTTPException(400, f"Operator not allowed: {k}")

            if k in ("$and", "$or"):
                if not isinstance(v, list) or not v:
                    raise HTTPException(400, f"{k} must be a non-empty list")
                if len(v) > 50:
                    raise HTTPException(400, f"{k} has too many clauses")
                for item in v:
                    if not isinstance(item, dict):
                        raise HTTPException(400, f"{k} items must be objects")
                    validate_query_obj(item, depth + 1)
                continue

            if k == "$regex":
                if not isinstance(v, str):
                    raise HTTPException(400, "$regex must be a string")
                if len(v) > MAX_REGEX_LENGTH:
                    raise HTTPException(400, "$regex is too long")
                continue

            if k == "$options":
                _validate_regex_options(v)
                continue

            if k in ("$in", "$nin"):
                if not isinstance(v, list):
                    raise HTTPException(400, f"{k} must be a list")
                if len(v) > MAX_IN_VALUES:
                    raise HTTPException(400, f"{k} list too large")
                continue

            validate_query_obj(v, depth + 1)
            continue

        if not _is_plain_field_key(k):
            raise HTTPException(400, "Invalid query key")

        if k in BLOCKED_QUERY_FIELDS:
            raise HTTPException(400, f"Field is enforced by the server and cannot be queried directly: {k}")

        validate_query_obj(v, depth + 1)
