from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any

from app.matchengine import MatchEngine

from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger


run_matchengine = require_scopes("detectionengine:run")

router = APIRouter(
    prefix="/detectionengine/matcher",
    tags=["matcher"],
)

matchengine = MatchEngine()
audit = AuditLogger()


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
    request: Request,
    identity=Depends(run_matchengine),
):
    """
    Uses a rule and log entry to find any matches.
    """

    try:

        result = matchengine(payload.rule, payload.log_data)

        body = RuleMatchResponse(
            matched=result["is_matched"],
            details=result["details"],
            rule=payload.rule,
            log_data=payload.log_data,
        )

        audit.log(
            event="matcher_rule_evaluated",
            identity=identity,
            request=request,
            metadata={
                "matched": result["is_matched"],
                "status": result["status"],
            },
        )

        return JSONResponse(
            status_code=result["status"],
            content=body.model_dump(),
        )

    except Exception as e:

        audit.log(
            event="matcher_rule_failed",
            identity=identity,
            request=request,
            result="failure",
            severity="ERROR",
            metadata={"error": str(e)},
        )

        raise


@router.get("/livez")
async def livez():
    """
    Liveness probe endpoint.
    """
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """
    Readiness probe endpoint.
    """
    return {"ready": True}