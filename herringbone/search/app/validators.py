from fastapi import HTTPException
from config import ALLOWED_OPERATORS

def validate_query_obj(obj, depth=0):
    if depth > 8:
        raise HTTPException(400, "Query too deep")

    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise HTTPException(400, "Invalid query key")
            if k.startswith("$") and k not in ALLOWED_OPERATORS:
                raise HTTPException(400, f"Operator not allowed: {k}")
            validate_query_obj(v, depth + 1)
        return

    if isinstance(obj, list):
        if len(obj) > 100:
            raise HTTPException(400, "Query list too large")
        for v in obj:
            validate_query_obj(v, depth + 1)
        return

    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return

    raise HTTPException(400, "Invalid query value type")
