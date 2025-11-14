from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from parser import CardParser

app = FastAPI(title="Extractor Service (FastAPI)")

# ---------- Pydantic models ----------

class Selector(BaseModel):
    type: str
    value: str

class Card(BaseModel):
    selector: Selector
    regex: Optional[List[Dict[str, str]]] = Field(default=None, description="List of {name: pattern}")
    jsonp: Optional[List[Dict[str, str]]] = Field(default=None, description="List of {name: jsonpath}")

class ExtractRequest(BaseModel):
    card: Card = Field(..., description="Full card JSON")
    input: Union[str, Dict[str, Any]] = Field(..., description="Raw log string or JSON object")

class ExtractResponse(BaseModel):
    selector: Dict[str, str]
    results: Dict[str, Any]

@app.post(
    "/parser/extractor/parse",
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

    # Regex
    if card.get("regex"):
        regex_parser = CardParser("regex")
        results.update(regex_parser(card["regex"], str(input_data)))

    # JSONPath
    if card.get("jsonp"):
        jsonp_parser = CardParser("jsonp")
        try:
            import json
            json_input = input_data if isinstance(input_data, dict) else json.loads(input_data)
            results.update(jsonp_parser(card["jsonp"], json_input))
        except Exception as e:
            results["jsonp_error"] = f"Invalid JSON input or evaluation error: {e}"

    return JSONResponse(content={"selector": selector, "results": results}, status_code=200)


#
# Herringbone requires Liveness and Readiness probes for all services.
#
# The routes below contain the logic for livez and readyz
#


@app.get("/parser/cardset/readyz")
def readyz():
    if getattr(app.state, "mongo", None) is None:
        return JSONResponse({"ok": False, "error": "mongo not ready"}, status_code=503)
    return {"ok": True}


@app.get("/parser/cardset/livez")
def livez():
    return {"ok": True}