import json
from typing import Optional, Dict, Any
from fastapi import HTTPException
from validators import validate_query_obj

def parse_q_string(q: Optional[str]) -> Dict[str, Any]:
    if not q:
        return {}

    try:
        obj = json.loads(q)
    except Exception:
        raise HTTPException(400, "q must be valid JSON")

    if not isinstance(obj, dict):
        raise HTTPException(400, "q must be a JSON object")

    if len(obj) > 20:
        raise HTTPException(400, "Too many query fields")

    for k in obj.keys():
        if not isinstance(k, str) or k.startswith("$") or "$" in k:
            raise HTTPException(400, "Invalid query key")

    validate_query_obj(obj)
    return obj
