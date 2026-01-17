from typing import Any
from fastapi import HTTPException
from config import ALLOWED_OPERATORS

def _is_plain_field_key(k: str) -> bool:
    if not isinstance(k, str):
        return False
    if k.startswith("$"):
        return False
    if "$" in k:
        return False
    return True

def validate_query_obj(obj: Any, depth: int = 0) -> None:
    if depth > 12:
        raise HTTPException(400, "Query too deep")

    if isinstance(obj, list):
        for item in obj:
            validate_query_obj(item, depth + 1)
        return

    if not isinstance(obj, dict):
        return

    for k, v in obj.items():
        if k.startswith("$"):
            if k not in ALLOWED_OPERATORS:
                raise HTTPException(400, f"Operator not allowed: {k}")

            if k in ("$and", "$or", "$nor"):
                if not isinstance(v, list) or not v:
                    raise HTTPException(400, f"{k} must be a non-empty list")
                for item in v:
                    if not isinstance(item, dict):
                        raise HTTPException(400, f"{k} items must be objects")
                    validate_query_obj(item, depth + 1)
                continue

            if k == "$regex":
                if not isinstance(v, str):
                    raise HTTPException(400, "$regex must be a string")
                continue

            if k in ("$in", "$nin"):
                if not isinstance(v, list):
                    raise HTTPException(400, f"{k} must be a list")
                continue

            validate_query_obj(v, depth + 1)
            continue

        if not _is_plain_field_key(k):
            raise HTTPException(400, "Invalid query key")

        validate_query_obj(v, depth + 1)
