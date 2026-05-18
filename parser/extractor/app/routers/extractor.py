import json
import os
import time
import traceback

try:
    import orjson
except Exception:  # optional fast-path dependency
    orjson = None
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from jose import JWTError, jwt

from app.parser import CardParser
from modules.auth.auth import require_internal_scopes
from modules.audit.logger import AuditLogger


# --------------------------------------------------------------------
# Quiet local service-token auth
# --------------------------------------------------------------------
# The shared auth dependency logs auth_service_token_valid on every successful
# service-token request. That is useful for interactive APIs, but very noisy
# for this hot internal extractor endpoint. By default the extractor validates
# the same RS256 service token locally and only audits auth failures.
#
# Set EXTRACTOR_QUIET_AUTH=false to fall back to the shared auth dependency.
EXTRACTOR_QUIET_AUTH = os.environ.get("EXTRACTOR_QUIET_AUTH", "true").lower() == "true"
SERVICE_JWT_PUBLIC_KEY_PATH = os.environ.get(
    "SERVICE_JWT_PUBLIC_KEY_PATH",
    "/run/secrets/service_jwt_public_key",
)
SERVICE_JWT_AUDIENCE = os.environ.get("SERVICE_JWT_AUDIENCE", "herringbone-services")
SERVICE_JWT_ALGORITHM = os.environ.get("SERVICE_JWT_ALGORITHM", "RS256")
AUDIT_EXTRACTOR_AUTH_FAILURES = os.environ.get(
    "AUDIT_EXTRACTOR_AUTH_FAILURES",
    "true",
).lower() == "true"

_PUBLIC_KEY_CACHE = None


def _get_public_key() -> str:
    global _PUBLIC_KEY_CACHE
    if _PUBLIC_KEY_CACHE is None:
        with open(SERVICE_JWT_PUBLIC_KEY_PATH, "r") as f:
            _PUBLIC_KEY_CACHE = f.read()
    return _PUBLIC_KEY_CACHE


def _normalize_scopes(raw_scopes):
    if raw_scopes is None:
        return []
    if isinstance(raw_scopes, str):
        return [s for s in raw_scopes.replace(",", " ").split() if s]
    if isinstance(raw_scopes, (list, tuple, set)):
        return [str(s) for s in raw_scopes]
    return []


def _audit_auth_failure(request: Request, reason: str):
    if not AUDIT_EXTRACTOR_AUTH_FAILURES:
        return
    try:
        audit.log(
            event="extractor_auth_failed",
            severity="WARNING",
            result="failure",
            request=request,
            metadata={"reason": reason},
        )
    except Exception:
        # Auth failure auditing must never break auth handling.
        pass


async def quiet_extractor_call_scope(request: Request):
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        _audit_auth_failure(request, "missing_bearer_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        _audit_auth_failure(request, "empty_bearer_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        try:
            claims = jwt.decode(
                token,
                _get_public_key(),
                algorithms=[SERVICE_JWT_ALGORITHM],
                audience=SERVICE_JWT_AUDIENCE,
            )
        except JWTError:
            # Some local/dev service tokens may not include aud. Keep support
            # for those without reintroducing noisy success audit logs.
            claims = jwt.decode(
                token,
                _get_public_key(),
                algorithms=[SERVICE_JWT_ALGORITHM],
                options={"verify_aud": False},
            )
    except Exception as e:
        _audit_auth_failure(request, f"invalid_token:{e.__class__.__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )

    scopes = _normalize_scopes(claims.get("scope") or claims.get("scopes"))
    if "extractor:call" not in scopes and "*" not in scopes:
        _audit_auth_failure(request, "missing_extractor_call_scope")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope: extractor:call",
        )

    return {
        "token_type": claims.get("typ") or claims.get("token_type") or "service",
        "service_id": claims.get("sub") or claims.get("service_id"),
        "service_name": claims.get("service") or claims.get("service_name"),
        "context_id": claims.get("context_id") or request.headers.get("X-Herringbone-Context"),
        "scopes": scopes,
        "claims": claims,
    }


extractor_call_scope = quiet_extractor_call_scope if EXTRACTOR_QUIET_AUTH else require_internal_scopes("extractor:call")

router = APIRouter(
    prefix="/parser/extractor",
    tags=["extractor"],
)

audit = AuditLogger()

EXTRACTOR_HEARTBEAT_ENABLED = os.environ.get("EXTRACTOR_HEARTBEAT_ENABLED", "true").lower() == "true"
EXTRACTOR_HEARTBEAT_INTERVAL = float(os.environ.get("EXTRACTOR_HEARTBEAT_INTERVAL", "5.0"))

_extractor_metrics = {
    "last_log": time.perf_counter(),
    "requests": 0,
    "batch_requests": 0,
    "single_requests": 0,
    "items": 0,
    "success": 0,
    "failed": 0,
    "fields": 0,
    "duration_ms": 0.0,
    "max_batch_size": 0,
    "errors_by_type": defaultdict(int),
}


def _record_extractor_metrics(
    *,
    items: int,
    success: int,
    failed: int,
    total_fields: int,
    duration_ms: float,
    batch: bool,
    error_types: Optional[Dict[str, int]] = None,
):
    _extractor_metrics["requests"] += 1
    _extractor_metrics["items"] += int(items or 0)
    _extractor_metrics["success"] += int(success or 0)
    _extractor_metrics["failed"] += int(failed or 0)
    _extractor_metrics["fields"] += int(total_fields or 0)
    _extractor_metrics["duration_ms"] += float(duration_ms or 0.0)
    _extractor_metrics["max_batch_size"] = max(
        int(_extractor_metrics["max_batch_size"]),
        int(items or 0),
    )

    if batch:
        _extractor_metrics["batch_requests"] += 1
    else:
        _extractor_metrics["single_requests"] += 1

    for error_type, count in (error_types or {}).items():
        _extractor_metrics["errors_by_type"][str(error_type)] += int(count or 0)

    _maybe_log_extractor_heartbeat()


def _maybe_log_extractor_heartbeat(force: bool = False):
    if not EXTRACTOR_HEARTBEAT_ENABLED:
        return

    t = time.perf_counter()
    elapsed = t - float(_extractor_metrics["last_log"])

    if not force and elapsed < EXTRACTOR_HEARTBEAT_INTERVAL:
        return

    requests_count = int(_extractor_metrics["requests"])
    items = int(_extractor_metrics["items"])
    success = int(_extractor_metrics["success"])
    failed = int(_extractor_metrics["failed"])
    duration_ms = float(_extractor_metrics["duration_ms"])

    if requests_count == 0 and not force:
        _extractor_metrics["last_log"] = t
        return

    audit.log(
        event="extractor_heartbeat",
        severity="INFO",
        result="success" if failed == 0 else "partial",
        metadata={
            "interval_sec": round(max(elapsed, 0.001), 3),
            "requests": requests_count,
            "batch_requests": int(_extractor_metrics["batch_requests"]),
            "single_requests": int(_extractor_metrics["single_requests"]),
            "items": items,
            "success": success,
            "failed": failed,
            "fields": int(_extractor_metrics["fields"]),
            "items_per_sec": round(items / max(elapsed, 0.001), 2),
            "requests_per_sec": round(requests_count / max(elapsed, 0.001), 2),
            "avg_request_ms": round(duration_ms / requests_count, 3) if requests_count else 0.0,
            "avg_item_ms": round(duration_ms / items, 3) if items else 0.0,
            "max_batch_size": int(_extractor_metrics["max_batch_size"]),
            "errors_by_type": dict(_extractor_metrics["errors_by_type"]),
        },
    )

    _extractor_metrics["last_log"] = t
    _extractor_metrics["requests"] = 0
    _extractor_metrics["batch_requests"] = 0
    _extractor_metrics["single_requests"] = 0
    _extractor_metrics["items"] = 0
    _extractor_metrics["success"] = 0
    _extractor_metrics["failed"] = 0
    _extractor_metrics["fields"] = 0
    _extractor_metrics["duration_ms"] = 0.0
    _extractor_metrics["max_batch_size"] = 0
    _extractor_metrics["errors_by_type"].clear()


# --------------------------------------------------------------------
# Performance / debug controls
# --------------------------------------------------------------------
AUDIT_EXTRACTOR_SUCCESS = os.environ.get("AUDIT_EXTRACTOR_SUCCESS", "false").lower() == "true"
AUDIT_EXTRACTOR_ERRORS = os.environ.get("AUDIT_EXTRACTOR_ERRORS", "true").lower() == "true"
EXTRACTOR_DEBUG_ERRORS = os.environ.get("EXTRACTOR_DEBUG_ERRORS", "true").lower() == "true"
EXTRACTOR_TIMING_HEADER = os.environ.get("EXTRACTOR_TIMING_HEADER", "true").lower() == "true"
EXTRACTOR_USE_ORJSON = os.environ.get("EXTRACTOR_USE_ORJSON", "true").lower() == "true"
EXTRACTOR_GROUP_BATCH_BY_CARD = os.environ.get("EXTRACTOR_GROUP_BATCH_BY_CARD", "true").lower() == "true"
EXTRACTOR_MAX_BATCH_ITEMS = int(os.environ.get("EXTRACTOR_MAX_BATCH_ITEMS", "5000"))

MAX_ERROR_LEN = int(os.environ.get("EXTRACTOR_MAX_ERROR_LEN", "500"))
MAX_TRACE_LEN = int(os.environ.get("EXTRACTOR_MAX_TRACE_LEN", "1500"))

# Reuse parser objects instead of instantiating them per item.
REGEX_PARSER = CardParser("regex")
JSONP_PARSER = CardParser("jsonp")


class Selector(BaseModel):
    type: str
    value: str
    # Excludes live inside selector according to CardSchema.
    # Pydantic model is only used by /parse; /parse/batch uses raw dicts.
    not_: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(default=None, alias="not")
    and_not: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(default=None)
    excludes: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(default=None)
    exclude: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(default=None)

    class Config:
        populate_by_name = True
        extra = "allow"


class Card(BaseModel):
    selector: Selector
    regex: Optional[List[Dict[str, str]]] = Field(default=None)
    jsonp: Optional[List[Dict[str, str]]] = Field(default=None)

    class Config:
        extra = "allow"


class ExtractRequest(BaseModel):
    card: Card
    input: Union[str, Dict[str, Any]]


class ExtractResponse(BaseModel):
    selector: Dict[str, str]
    results: Dict[str, Any]


# Kept for docs/backward compatibility, but /parse/batch now uses raw JSON
# instead of Pydantic model validation for high-throughput internal calls.
class BatchExtractItem(BaseModel):
    event_id: Union[str, int]
    card: Card
    card_name: Optional[str] = None
    input: Union[str, Dict[str, Any]]


class BatchExtractRequest(BaseModel):
    context_id: Optional[str] = None
    items: List[BatchExtractItem] = Field(default_factory=list, max_length=1000)


class BatchExtractResult(BaseModel):
    event_id: Union[str, int]
    card: Optional[str] = None
    success: bool
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    error_stage: Optional[str] = None


class BatchExtractResponse(BaseModel):
    results: List[BatchExtractResult]


def _response(content: Dict[str, Any], status_code: int = 200, headers: Optional[Dict[str, str]] = None):
    """
    Fast JSON response without FastAPI ORJSONResponse.

    Newer FastAPI versions emit a deprecation warning for ORJSONResponse.
    Returning a raw Response with orjson.dumps keeps the fast serialization path
    and avoids the warning.
    """
    headers = headers or {}
    if EXTRACTOR_USE_ORJSON and orjson is not None:
        try:
            return Response(
                content=orjson.dumps(content),
                status_code=status_code,
                headers=headers,
                media_type="application/json",
            )
        except Exception:
            # If an unexpected non-serializable value slips through, preserve behavior.
            return JSONResponse(content=content, status_code=status_code, headers=headers)

    return JSONResponse(content=content, status_code=status_code, headers=headers)


def _short(value: Any, max_len: int = MAX_ERROR_LEN) -> str:
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...[truncated]"


def _error_payload(exc: Exception, stage: str) -> Dict[str, str]:
    payload = {
        "error": _short(exc),
        "error_type": exc.__class__.__name__,
        "error_stage": stage,
    }

    if EXTRACTOR_DEBUG_ERRORS:
        payload["trace"] = _short(traceback.format_exc(), MAX_TRACE_LEN)

    return payload


def _as_card_dict(card: Any) -> Dict[str, Any]:
    """Accept either raw dict cards or Pydantic cards."""
    if isinstance(card, dict):
        return card
    if hasattr(card, "model_dump"):
        return card.model_dump()
    if hasattr(card, "dict"):
        return card.dict()
    return {}


def _card_label(card: Dict[str, Any], card_name: Optional[str] = None) -> str:
    if card_name:
        return card_name

    selector = card.get("selector") or {}
    stype = selector.get("type", "")
    value = selector.get("value", "")
    return f"{stype}:{value}" if stype or value else "unknown-card"


def _card_signature(card: Dict[str, Any], card_name: Optional[str] = None) -> str:
    """
    Stable-ish grouping key so a batch with many jobs for the same card can avoid
    repeatedly normalizing labels and walking card metadata.
    """
    selector = card.get("selector") or {}
    regex_rules = card.get("regex") or []
    jsonp_rules = card.get("jsonp") or []
    return json.dumps(
        {
            "name": card_name or "",
            "selector": selector,
            "regex": regex_rules,
            "jsonp": jsonp_rules,
            "excludes": card.get("excludes") or card.get("exclude") or [],
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def _normalize_selector_list(value: Any) -> List[dict]:
    if not value:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    return []


def _selector_matches_input(selector: Dict[str, Any], input_data: Union[str, Dict[str, Any]]) -> bool:
    if not isinstance(selector, dict):
        return False

    stype = str(selector.get("type") or "").strip().lower()
    value = selector.get("value")
    if value is None or value == "":
        return False

    text = input_data if isinstance(input_data, str) else json.dumps(input_data, default=str)
    value_s = str(value)

    if stype in {"raw", "contains", "raw_contains", "substring"}:
        return value_s in text
    if stype in {"not_contains", "raw_not_contains"}:
        return value_s not in text
    if stype in {"equals", "raw_equals"}:
        return text == value_s
    if stype in {"startswith", "starts_with", "raw_startswith", "raw_starts_with"}:
        return text.startswith(value_s)
    if stype in {"endswith", "ends_with", "raw_endswith", "raw_ends_with"}:
        return text.endswith(value_s)
    if stype in {"raw_regex", "regex", "matches"}:
        return re.search(value_s, text, flags=re.IGNORECASE) is not None

    # source/path-style exclusions are usually enforced in enrichment where the
    # full event document exists. In extractor we only have the input payload.
    return False


def _is_excluded(card: Dict[str, Any], input_data: Union[str, Dict[str, Any]]) -> bool:
    selector = card.get("selector") or {}
    if not isinstance(selector, dict):
        return False

    negative_rules: List[dict] = []
    negative_rules.extend(_normalize_selector_list(selector.get("not")))
    negative_rules.extend(_normalize_selector_list(selector.get("and_not")))
    negative_rules.extend(_normalize_selector_list(selector.get("excludes")))
    negative_rules.extend(_normalize_selector_list(selector.get("exclude")))
    negative_rules.extend(_normalize_selector_list(card.get("excludes")))
    negative_rules.extend(_normalize_selector_list(card.get("exclude")))

    for negative_selector in negative_rules:
        try:
            if _selector_matches_input(negative_selector, input_data):
                return True
        except Exception:
            # Exclude evaluation must never break extraction. Bad exclude rules
            # simply fail closed as non-matches.
            continue

    return False


def _run_card(card: Dict[str, Any], input_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Shared extraction logic for both single-event and batch endpoints.

    Speedups:
      - Reuses global CardParser instances.
      - parser.py caches compiled regex patterns/jsonpaths.
      - Avoids JSON parsing unless jsonp rules exist.
    """
    results: Dict[str, Any] = {}

    if _is_excluded(card, input_data):
        return results

    regex_rules = card.get("regex")
    if regex_rules:
        # Most inputs are already raw strings; avoid unnecessary conversion work.
        text_input = input_data if isinstance(input_data, str) else str(input_data)
        results.update(REGEX_PARSER(regex_rules, text_input))

    jsonp_rules = card.get("jsonp")
    if jsonp_rules:
        try:
            json_input = input_data if isinstance(input_data, dict) else json.loads(input_data)
            results.update(JSONP_PARSER(jsonp_rules, json_input))
        except Exception as e:
            results["jsonp_error"] = f"Invalid JSON input or evaluation error: {e}"

    return results


def _audit_single_success_if_enabled(
    *,
    identity,
    request: Request,
    selector: Dict[str, str],
    results: Dict[str, Any],
    duration_ms: float,
):
    if not AUDIT_EXTRACTOR_SUCCESS:
        return

    audit.log(
        event="extractor_parse",
        severity="INFO",
        result="success",
        identity=identity,
        request=request,
        target=f"{selector.get('type')}:{selector.get('value')}",
        metadata={
            "fields": list(results.keys()),
            "field_count": len(results.keys()),
            "duration_ms": round(duration_ms, 3),
        },
    )


def _audit_single_error_if_enabled(
    *,
    identity,
    request: Request,
    selector: Dict[str, str],
    exc: Exception,
    duration_ms: float,
):
    if not AUDIT_EXTRACTOR_ERRORS:
        return

    err = _error_payload(exc, "single_parse")
    audit.log(
        event="extractor_parse_failed",
        severity="ERROR",
        result="failure",
        identity=identity,
        request=request,
        target=f"{selector.get('type')}:{selector.get('value')}",
        metadata={
            "duration_ms": round(duration_ms, 3),
            "error": err["error"],
            "error_type": err["error_type"],
            "error_stage": err["error_stage"],
            "trace": err.get("trace"),
        },
    )


def _audit_batch_if_needed(
    *,
    identity,
    request: Request,
    context_id: Optional[str],
    item_count: int,
    failed: int,
    total_fields: int,
    duration_ms: float,
    error_types: Counter,
    grouped_cards: int,
):
    if failed == 0 and not AUDIT_EXTRACTOR_SUCCESS:
        return

    jobs_per_sec = round(item_count / max(duration_ms / 1000.0, 0.001), 2)

    audit.log(
        event="extractor_parse_batch",
        severity="INFO" if failed == 0 else "ERROR",
        result="success" if failed == 0 else "partial_failure",
        identity=identity,
        request=request,
        target=f"context:{context_id or request.headers.get('X-Herringbone-Context', '')}",
        metadata={
            "items": item_count,
            "failed": failed,
            "total_fields": total_fields,
            "duration_ms": round(duration_ms, 3),
            "jobs_per_sec": jobs_per_sec,
            "context_id": context_id,
            "grouped_cards": grouped_cards,
            "error_types": dict(error_types),
        },
    )


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
    started = time.perf_counter()
    card = payload.card.model_dump()
    input_data = payload.input
    selector = card["selector"]

    try:
        results = _run_card(card, input_data)
        duration_ms = (time.perf_counter() - started) * 1000

        _audit_single_success_if_enabled(
            identity=identity,
            request=request,
            selector=selector,
            results=results,
            duration_ms=duration_ms,
        )

        _record_extractor_metrics(
            items=1,
            success=1,
            failed=0,
            total_fields=len(results) if isinstance(results, dict) else 0,
            duration_ms=duration_ms,
            batch=False,
        )

        headers = {}
        if EXTRACTOR_TIMING_HEADER:
            headers["X-Herringbone-Extractor-Duration-Ms"] = str(round(duration_ms, 3))

        return _response(
            content={"selector": selector, "results": results},
            status_code=200,
            headers=headers,
        )

    except Exception as e:
        duration_ms = (time.perf_counter() - started) * 1000
        _audit_single_error_if_enabled(
            identity=identity,
            request=request,
            selector=selector,
            exc=e,
            duration_ms=duration_ms,
        )

        _record_extractor_metrics(
            items=1,
            success=0,
            failed=1,
            total_fields=0,
            duration_ms=duration_ms,
            batch=False,
            error_types={e.__class__.__name__: 1},
        )

        return _response(
            content={
                "selector": selector,
                "results": {},
                "error": _short(e),
                "error_type": e.__class__.__name__,
                "error_stage": "single_parse",
            },
            status_code=500,
        )


@router.post(
    "/parse/batch",
    summary="Run regex and/or JSONPath extraction over many event/card jobs",
    description=(
        "Receives many event/card/input jobs and returns one result per job. "
        "Designed for parser-enrichment batch mode. Uses raw JSON parsing for high EPS."
    ),
)
async def parse_batch(
    request: Request,
    identity=Depends(extractor_call_scope),
):
    """
    High-throughput internal batch endpoint.

    It intentionally avoids Pydantic validation for every item. This endpoint is
    protected by internal service auth and receives payloads from parser-enrichment,
    so avoiding per-item model construction gives much better throughput.
    """
    started = time.perf_counter()
    batch_results: List[Dict[str, Any]] = []
    total_fields = 0
    failed = 0
    error_types: Counter = Counter()

    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception as e:
        duration_ms = (time.perf_counter() - started) * 1000
        err = _error_payload(e, "batch_payload_parse")
        _record_extractor_metrics(
            items=0,
            success=0,
            failed=1,
            total_fields=0,
            duration_ms=duration_ms,
            batch=True,
            error_types={e.__class__.__name__: 1},
        )
        return _response(
            content={
                "results": [],
                "error": err["error"],
                "error_type": err["error_type"],
                "error_stage": err["error_stage"],
            },
            status_code=400,
        )

    context_id = payload.get("context_id") or request.headers.get("X-Herringbone-Context")
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []

    if len(items) > EXTRACTOR_MAX_BATCH_ITEMS:
        items = items[:EXTRACTOR_MAX_BATCH_ITEMS]

    grouped_cards = 0

    def handle_item(item: Dict[str, Any], prepared_card: Optional[Dict[str, Any]] = None, prepared_label: Optional[str] = None):
        nonlocal total_fields, failed

        if not isinstance(item, dict):
            failed += 1
            error_types["InvalidItem"] += 1
            batch_results.append(
                {
                    "event_id": None,
                    "card": "unknown-card",
                    "success": False,
                    "error": "Batch item is not an object",
                    "error_type": "InvalidItem",
                    "error_stage": "batch_item_parse",
                }
            )
            return

        event_id = item.get("event_id")
        card_name = item.get("card") or item.get("card_name")
        card = prepared_card if prepared_card is not None else _as_card_dict(item.get("card") or {})
        card_label = prepared_label if prepared_label is not None else _card_label(card, card_name)
        input_data = item.get("input", "")

        try:
            results = _run_card(card, input_data)
            total_fields += len(results.keys())

            batch_results.append(
                {
                    "event_id": event_id,
                    "card": card_label,
                    "success": True,
                    "results": results,
                }
            )

        except Exception as e:
            failed += 1
            error_types[e.__class__.__name__] += 1
            err = _error_payload(e, "batch_item_parse")

            batch_results.append(
                {
                    "event_id": event_id,
                    "card": card_label,
                    "success": False,
                    "error": err["error"],
                    "error_type": err["error_type"],
                    "error_stage": err["error_stage"],
                }
            )

    if EXTRACTOR_GROUP_BATCH_BY_CARD and items:
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        prepared_by_sig: Dict[str, Dict[str, Any]] = {}
        label_by_sig: Dict[str, str] = {}

        for item in items:
            if not isinstance(item, dict):
                handle_item(item)
                continue
            card_name = item.get("card") or item.get("card_name")
            card = _as_card_dict(item.get("card") or {})
            sig = _card_signature(card, card_name)
            groups[sig].append(item)
            if sig not in prepared_by_sig:
                prepared_by_sig[sig] = card
                label_by_sig[sig] = _card_label(card, card_name)

        grouped_cards = len(groups)
        for sig, group_items in groups.items():
            prepared_card = prepared_by_sig[sig]
            prepared_label = label_by_sig[sig]
            for item in group_items:
                handle_item(item, prepared_card=prepared_card, prepared_label=prepared_label)
    else:
        for item in items:
            handle_item(item)

    duration_ms = (time.perf_counter() - started) * 1000

    _audit_batch_if_needed(
        identity=identity,
        request=request,
        context_id=context_id,
        item_count=len(items),
        failed=failed,
        total_fields=total_fields,
        duration_ms=duration_ms,
        error_types=error_types,
        grouped_cards=grouped_cards,
    )

    _record_extractor_metrics(
        items=len(items),
        success=max(0, len(items) - failed),
        failed=failed,
        total_fields=total_fields,
        duration_ms=duration_ms,
        batch=True,
        error_types=dict(error_types),
    )

    headers = {}
    if EXTRACTOR_TIMING_HEADER:
        headers["X-Herringbone-Extractor-Duration-Ms"] = str(round(duration_ms, 3))
        headers["X-Herringbone-Extractor-Jobs"] = str(len(items))
        headers["X-Herringbone-Extractor-Failed"] = str(failed)
        headers["X-Herringbone-Extractor-Fields"] = str(total_fields)

    return _response(
        content={"results": batch_results},
        status_code=200,
        headers=headers,
    )


@router.get("/readyz")
async def readyz():
    return {"ok": True}


@router.get("/livez")
async def livez():
    return {"ok": True}