from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, List, Optional

from app.matchengine import MatchEngine

from modules.auth.auth import require_internal_scopes
from modules.audit.logger import AuditLogger


run_matchengine = require_internal_scopes("detectionengine:run")

router = APIRouter(
    prefix="/detectionengine/matcher",
    tags=["matcher"],
)

matchengine = MatchEngine()
audit = AuditLogger()


class RuleMatchRequest(BaseModel):
    rule: Dict[str, Any] = Field(..., description="Rule JSON")
    log_data: Dict[str, Any] = Field(..., description="Log JSON to evaluate")

    model_config = ConfigDict(extra="allow")


class RuleMatchResponse(BaseModel):
    matched: bool
    details: str
    rule: Dict[str, Any]
    log_data: Dict[str, Any]


class BatchRuleMatchItem(BaseModel):
    item_id: Optional[str | int] = None
    rule: Dict[str, Any] = Field(..., description="Rule JSON")
    log_data: Dict[str, Any] = Field(..., description="Log JSON to evaluate")

    model_config = ConfigDict(extra="allow")


class BatchRuleMatchRequest(BaseModel):
    items: List[BatchRuleMatchItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class BatchRuleMatchResult(BaseModel):
    item_id: Optional[str | int] = None
    matched: bool
    details: str
    status: int = 200
    rule: Dict[str, Any]
    log_data: Dict[str, Any]


class BatchRuleMatchResponse(BaseModel):
    count: int
    matched_count: int
    results: List[BatchRuleMatchResult]


@router.post("/find_match", response_model=RuleMatchResponse)
async def find_match(
    payload: RuleMatchRequest,
    request: Request,
    identity=Depends(run_matchengine),
):
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
                "batch": False,
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
            metadata={"error": str(e), "batch": False},
        )
        raise


@router.post("/find_matches_batch", response_model=BatchRuleMatchResponse)
async def find_matches_batch(
    payload: BatchRuleMatchRequest,
    request: Request,
    identity=Depends(run_matchengine),
):
    try:
        raw_items = [item.model_dump() for item in payload.items]
        results = matchengine.match_many(raw_items)
        matched_count = sum(1 for item in results if item.get("matched"))

        body = BatchRuleMatchResponse(
            count=len(results),
            matched_count=matched_count,
            results=[BatchRuleMatchResult(**item) for item in results],
        )

        audit.log(
            event="matcher_batch_evaluated",
            identity=identity,
            request=request,
            metadata={
                "count": len(results),
                "matched_count": matched_count,
                "batch": True,
            },
        )

        return body

    except Exception as e:
        audit.log(
            event="matcher_batch_failed",
            identity=identity,
            request=request,
            result="failure",
            severity="ERROR",
            metadata={"error": str(e), "batch": True},
        )
        raise


@router.get("/livez")
async def livez():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    return {"ready": True}
