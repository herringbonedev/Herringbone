from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any
from app.matchengine import MatchEngine
from modules.auth.service import require_service_scope

run_matchengine = require_service_scope("detectionengine:run")

router = APIRouter(
    prefix="/detectionengine/matcher",
    tags=["matcher"],
)

matchengine = MatchEngine()

class RuleMatchRequest(BaseModel):
    """
    Input to the matcher microservice.
    Contains the rule JSON and the log JSON.
    """
    rule: Dict[str, Any] = Field(..., description="Rule JSON")
    log_data: Dict[str, Any] = Field(..., description="Log JSON to evaluate")
    model_config = ConfigDict(extra="allow")


class RuleMatchResponse(BaseModel):
    """
    Output from the matcher microservice.
    """
    matched: bool
    details: str
    rule: Dict[str, Any]
    log_data: Dict[str, Any]

@router.post("/find_match", response_model=RuleMatchResponse)
async def find_match(
    payload: RuleMatchRequest,
    service=Depends(run_matchengine)
):
    """
    Uses a rule and log entry to find any matches.
    """
    result = matchengine(payload.rule, payload.log_data)
    print(result)

    body = RuleMatchResponse(
        matched=result["is_matched"],
        details=result["details"],
        rule=payload.rule,
        log_data=payload.log_data,
    )

    return JSONResponse(
        status_code=result["status"],
        content=body.model_dump()
    )


@router.get("/livez")
async def livez():
    """
    Liveness probe endpoint.
    """
    return "OK"


@router.get("/readyz")
async def readyz():
    """
    Readiness probe endpoint.
    """
    return "OK"