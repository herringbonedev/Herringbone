from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from parser import CardParser
import json

router = APIRouter(
    prefix="/parser/extractor",
    tags=["extractor"],
)

class Selector(BaseModel):
    type: str
    value: str

class Card(BaseModel):
    selector: Selector
    regex: Optional[List[Dict[str, str]]] = Field(default=None)
    jsonp: Optional[List[Dict[str, str]]] = Field(default=None)

class ExtractRequest(BaseModel):
    card: Card
    input: Union[str, Dict[str, Any]]

class ExtractResponse(BaseModel):
    selector: Dict[str, str]
    results: Dict[str, Any]


@router.post(
    "/parse",
    response_model=ExtractResponse,
    summary="Run regex and/or JSONPath extraction over input",
    description="Receives a full card and an input (string or JSON) and returns {selector, results}."
)
async def parse(payload: ExtractRequest):
    card = payload.card.model_dump()
    input_data = payload.input
    selector = card["selector"]
    results: Dict[str, Any] = {}
    print(f"[→] Using card: {str(card)} to parse {str(input_data)}")

    if card.get("regex"):
        regex_parser = CardParser("regex")
        results.update(regex_parser(card["regex"], str(input_data)))

    if card.get("jsonp"):
        jsonp_parser = CardParser("jsonp")
        try:
            json_input = input_data if isinstance(input_data, dict) else json.loads(input_data)
            results.update(jsonp_parser(card["jsonp"], json_input))
        except Exception as e:
            results["jsonp_error"] = f"Invalid JSON input or evaluation error: {e}"

    return JSONResponse(content={"results": results}, status_code=200)


@router.get("/readyz")
async def readyz():
    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
        return {"ok": True}
    except Exception:
        return JSONResponse({"ok": False, "error": "mongo not ready"}, status_code=503)
    finally:
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass


@router.get("/livez")
async def livez():
    return {"ok": True}
