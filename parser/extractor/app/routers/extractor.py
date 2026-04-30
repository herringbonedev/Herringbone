from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from app.parser import CardParser
import json

from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger

extractor_call_scope = require_scopes("extractor:call")

router = APIRouter(
    prefix="/parser/extractor",
    tags=["extractor"],
)

audit = AuditLogger()


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
    description="Receives a full card and an input (string or JSON) and returns {selector, results}.",
)
async def parse(
    payload: ExtractRequest,
    request: Request,
    identity=Depends(extractor_call_scope),
):
    card = payload.card.model_dump()
    input_data = payload.input
    selector = card["selector"]
    results: Dict[str, Any] = {}

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

    audit.log(
        event="extractor_parse",
        severity="INFO",
        identity=identity,
        request=request,
        target=f"{selector.get('type')}:{selector.get('value')}",
        metadata={"fields": list(results.keys())},
    )

    return JSONResponse(content={"selector": selector, "results": results}, status_code=200)


@router.get("/readyz")
async def readyz():
    return {"ok": True}


@router.get("/livez")
async def livez():
    return {"ok": True}