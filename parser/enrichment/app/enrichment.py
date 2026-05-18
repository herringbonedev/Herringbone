from datetime import datetime, timezone, timedelta
import os
import time
import requests
import socket
import re
from time import time as now
from typing import Any, Dict, Iterable, List, Optional, Tuple
from bson import ObjectId

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.database.mongo_bulk import HerringboneMongoBulkOperations
from modules.audit.logger import AuditLogger


POLL_INTERVAL = float(os.environ.get("ENRICHMENT_POLL_INTERVAL", 0.001))
CARD_CACHE_SECONDS = float(os.environ.get("CARD_CACHE_SECONDS", 300.0))
ENRICHMENT_BATCH_SIZE = int(os.environ.get("ENRICHMENT_BATCH_SIZE", 500))
EXTRACTOR_BATCH_SIZE = int(os.environ.get("EXTRACTOR_BATCH_SIZE", 250))
CLAIM_LEASE_SECONDS = int(os.environ.get("CLAIM_LEASE_SECONDS", 300))
DEBUG_BATCH_CLAIMS = os.environ.get("DEBUG_BATCH_CLAIMS", "false").lower() == "true"
DEBUG_BATCH_COUNTS = os.environ.get("DEBUG_BATCH_COUNTS", "false").lower() == "true"
AUTO_DISCOVER_CONTEXTS = os.environ.get("AUTO_DISCOVER_CONTEXTS", "false").lower() == "true"
INCLUDE_MISSING_DEFAULT_CONTEXT = os.environ.get("INCLUDE_MISSING_DEFAULT_CONTEXT", "false").lower() == "true"
EXTRACTOR_FALLBACK_ENABLED = os.environ.get("EXTRACTOR_FALLBACK_ENABLED", "true").lower() == "true"

EXTRACTOR_SVC = os.environ.get("EXTRACTOR_SVC")
EXTRACTOR_BATCH_SVC = os.environ.get("EXTRACTOR_BATCH_SVC")
USE_TEST = EXTRACTOR_SVC == "test.service"
ENTERPRISE_MODE = os.environ.get("HB_ENTERPRISE", "false").lower() == "true"
DEFAULT_CONTEXT_ID = os.environ.get("CONTEXT_ID", "default")

SERVICE_TOKEN_PATH = "/run/secrets/service_token"
INSTANCE_ID = socket.gethostname()

audit = AuditLogger()

_metrics = {
    "processed": 0,
    "matched_cards": 0,
    "failed": 0,
    "batches": 0,
    "last_log": 0.0,
}

_card_cache = {
    "context_id": None,
    "cards": [],
    "prepared": None,
    "loaded_at": 0.0,
}

print("[*] Enrichment service has started")
print(f"[*] Batch mode enabled batch_size={ENRICHMENT_BATCH_SIZE} extractor_batch_size={EXTRACTOR_BATCH_SIZE}")

if USE_TEST:
    print("[*] [Test Service] Started in test mode")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def chunks(items: List[Any], size: int) -> Iterable[List[Any]]:
    if size <= 0:
        size = 100
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _maybe_log(interval: float = 5.0):
    t = now()
    if t - _metrics["last_log"] < interval:
        return

    rate = _metrics["processed"] / max(interval, 1)
    audit.log(
        event="parser_heartbeat",
        metadata={
            "processed": _metrics["processed"],
            "matched_cards": _metrics["matched_cards"],
            "failed": _metrics["failed"],
            "batches": _metrics["batches"],
            "rate_per_sec": round(rate, 2),
            "batch_size": ENRICHMENT_BATCH_SIZE,
            "extractor_batch_size": EXTRACTOR_BATCH_SIZE,
        },
    )
    _metrics["processed"] = 0
    _metrics["matched_cards"] = 0
    _metrics["failed"] = 0
    _metrics["batches"] = 0
    _metrics["last_log"] = t


def resolve_context_id(state: Optional[dict] = None, event: Optional[dict] = None) -> str:
    context_id = ((state or {}).get("context_id") or (event or {}).get("context_id"))
    if context_id:
        return context_id
    if ENTERPRISE_MODE and not USE_TEST:
        raise RuntimeError("missing context_id: refusing to process event in enterprise mode")
    return DEFAULT_CONTEXT_ID


def service_auth_headers(context_id: str = DEFAULT_CONTEXT_ID):
    with open(SERVICE_TOKEN_PATH, "r") as f:
        token = f.read().strip()
    return {
        "Authorization": f"Bearer {token}",
        "X-Herringbone-Context": context_id,
    }


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


def get_bulk_mongo():
    return HerringboneMongoBulkOperations(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
        max_pool_size=int(os.environ.get("MONGO_BULK_MAX_POOL_SIZE", 100)),
    )


def _looks_like_pymongo_database(value) -> bool:
    """
    Avoid treating a string database name like an actual PyMongo Database object.
    PyMongo Database objects support collection access and expose list_collection_names().
    """
    return (
        value is not None
        and not isinstance(value, str)
        and hasattr(value, "__getitem__")
        and hasattr(value, "list_collection_names")
    )


def get_raw_db(mongo):
    """
    Best-effort access to the underlying PyMongo database.

    Important:
      Some HerringboneMongoDatabase wrappers use `database` as a plain string
      database name. Returning that string causes errors like:
        string indices must be integers, not 'str'
      when code later does db["event_state"].

    This function only returns an object that looks like a real PyMongo Database.
    Otherwise it returns None and the worker falls back to wrapper methods.
    """
    for attr in ("db", "_db", "database"):
        value = getattr(mongo, attr, None)
        if _looks_like_pymongo_database(value):
            return value

    client = getattr(mongo, "client", None) or getattr(mongo, "_client", None)
    if client is not None and not isinstance(client, str):
        try:
            return client[os.environ.get("DB_NAME", "herringbone")]
        except Exception:
            return None

    return None


def _json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            k: _json_safe(v)
            for k, v in value.items()
            if not str(k).startswith("_")
        }

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    # Compiled regex objects are not JSON serializable.
    # They are runtime-only cache fields and should never be sent to extractor.
    if hasattr(value, "pattern") and hasattr(value, "search"):
        return getattr(value, "pattern", str(value))

    return value


def sanitize_card(card: dict) -> dict:
    return {
        k: _json_safe(v)
        for k, v in card.items()
        if k != "_id" and not str(k).startswith("_")
    }


def safe_card_label(card: dict) -> str:
    """Return a stable string label for a card.

    Some card documents may have non-scalar name fields. Never use raw card
    values directly as dict keys; normalize to a string first.
    """
    if not isinstance(card, dict):
        return "unknown-card"

    for key in ("name", "card", "card_name", "id", "_id"):
        value = card.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return str(value)

    selector = card.get("selector") or {}
    stype = selector.get("type", "") if isinstance(selector, dict) else ""
    value = selector.get("value", "") if isinstance(selector, dict) else ""
    if stype or value:
        return f"{stype}:{value}"

    return "unknown-card"


def safe_result_card_label(result: dict) -> str:
    if not isinstance(result, dict):
        return "unknown-card"
    value = result.get("card") or result.get("card_name")
    if value is None:
        return "unknown-card"
    return str(value)


def selector_matches(selector: dict, event: dict) -> bool:
    stype = selector.get("type")
    value = selector.get("value")
    if not value:
        return False

    raw = event.get("raw", "") or ""

    # Existing behavior: exact source.address match
    if stype == "source_address":
        return event.get("source", {}).get("address") == value

    # Existing behavior: simple raw substring match
    if stype == "raw":
        return str(value) in raw

    # New behavior: regex selector against raw log
    if stype == "raw_regex":
        try:
            return re.search(str(value), raw) is not None
        except re.error as e:
            audit.log(
                event="parser_selector_regex_failed",
                result="failure",
                severity="WARNING",
                metadata={
                    "selector_type": stype,
                    "pattern": str(value),
                    "error": str(e),
                },
            )
            return False

    return False


def normalize_results(results: dict) -> dict:
    normalized = {}
    for k, v in results.items():
        normalized[k] = v if isinstance(v, list) else [v]
    return normalized


def run_regex_rules(card: dict, raw_log: str) -> dict:
    results = {}
    compiled_rules = card.get("_compiled_regex")
    if compiled_rules is not None:
        for rule in compiled_rules:
            m = rule["regex"].search(raw_log or "")
            if m:
                results[rule["name"]] = [m.group(0)]
        return results

    for rule in card.get("regex") or []:
        if "pattern" not in rule or "name" not in rule:
            continue
        m = re.search(rule["pattern"], raw_log or "")
        if m:
            results[rule["name"]] = [m.group(0)]
    return results


def call_extractor(card: dict, raw_log: str, context_id: str = DEFAULT_CONTEXT_ID) -> dict:
    if not EXTRACTOR_SVC:
        raise RuntimeError("EXTRACTOR_SVC is not set")
    payload = {"card": sanitize_card(card), "input": raw_log}
    resp = requests.post(
        EXTRACTOR_SVC,
        json=payload,
        headers=service_auth_headers(context_id),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], dict):
        return data["results"]
    raise RuntimeError("Extractor returned invalid result shape")


def call_extractor_batch_with_retry(jobs, context_id, attempts=3):
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            return call_extractor_batch(jobs, context_id)

        except requests.exceptions.RequestException as e:
            last_error = e

            audit.log(
                event="extractor_batch_retryable_failure",
                severity="WARNING" if attempt < attempts else "ERROR",
                result="retry" if attempt < attempts else "failure",
                metadata={
                    "context_id": context_id,
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "jobs": len(jobs),
                    "extractor_batch_svc": EXTRACTOR_BATCH_SVC,
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "sleep_seconds": round(0.25 * attempt, 3) if attempt < attempts else 0,
                },
            )

            if attempt < attempts:
                time.sleep(0.25 * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError("No retry attempts were executed or no retryable exception was captured")


def call_extractor_compat(card: dict, raw_log: str, context_id: str) -> dict:
    try:
        return call_extractor(card, raw_log, context_id)
    except TypeError:
        return call_extractor(card, raw_log)  # type: ignore[misc]


def call_extractor_batch(jobs: List[dict], context_id: str) -> List[dict]:
    if not jobs:
        return []

    if EXTRACTOR_BATCH_SVC:
        payload = {
            "context_id": context_id,
            "items": [
                {
                    "event_id": str(job["event_id"]),
                    "card": sanitize_card(job["card"]),
                    "card_name": safe_card_label(job["card"]),
                    "input": job.get("raw", ""),
                }
                for job in jobs
            ],
        }
        resp = requests.post(
            EXTRACTOR_BATCH_SVC,
            json=payload,
            headers=service_auth_headers(context_id),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise RuntimeError("Batch extractor returned invalid result shape")
        return results

    output = []
    for job in jobs:
        try:
            raw_result = call_extractor_compat(job["card"], job.get("raw", ""), context_id)
            if not isinstance(raw_result, dict):
                raise RuntimeError("Extractor returned invalid result shape")
            output.append({
                "event_id": job["event_id"],
                "card": job["card"].get("name"),
                "success": True,
                "results": normalize_results(raw_result),
            })
        except Exception as e:
            output.append({
                "event_id": job["event_id"],
                "card": job["card"].get("name"),
                "success": False,
                "error": str(e),
            })
    return output


def compile_card_regex(card: dict) -> dict:
    compiled = []
    for rule in card.get("regex") or []:
        if "pattern" not in rule or "name" not in rule:
            continue
        try:
            compiled.append({
                "name": rule["name"],
                "regex": re.compile(rule["pattern"]),
            })
        except re.error as e:
            audit.log(
                event="parser_card_regex_compile_failed",
                result="failure",
                severity="WARNING",
                metadata={
                    "card": card.get("name"),
                    "pattern": rule.get("pattern"),
                    "error": str(e),
                },
            )
    card["_compiled_regex"] = compiled
    return card


def prepare_cards(cards: List[dict]) -> dict:
    """
    Pre-group cards so each event does not blindly scan all selectors where possible.
    This stays generic to card selector types:
      - source_address selector: O(1) lookup
      - raw selector: substring checks only for raw selector cards
      - other selector types: conservative fallback list
    """
    prepared = {
        "source_address": {},
        "raw": [],
        "other": [],
        "total": len(cards),
    }

    for card in cards:
        card = compile_card_regex(card)
        selector = card.get("selector") or {}
        stype = selector.get("type")
        value = selector.get("value")
        if not value:
            prepared["other"].append(card)
            continue
        if stype == "source_address":
            prepared["source_address"].setdefault(value, []).append(card)
        elif stype == "raw":
            prepared["raw"].append(card)
        else:
            prepared["other"].append(card)
    return prepared


def get_cards_cached(mongo, context_id: str):
    t = now()
    if (_card_cache["context_id"] == context_id and _card_cache["cards"] and t - _card_cache["loaded_at"] < CARD_CACHE_SECONDS):
        return _card_cache["cards"]
    cards = mongo.find_with_context("parse_cards", {}, context_id=context_id)
    _card_cache["context_id"] = context_id
    _card_cache["cards"] = cards
    _card_cache["prepared"] = prepare_cards(cards)
    _card_cache["loaded_at"] = t
    return cards


def get_prepared_cards_cached(mongo, context_id: str):
    get_cards_cached(mongo, context_id)
    return _card_cache.get("prepared") or prepare_cards(_card_cache.get("cards") or [])


def matching_cards_for_event(prepared: dict, event: dict) -> List[dict]:
    raw = event.get("raw", "") or ""
    source_address = event.get("source", {}).get("address")
    matched: List[dict] = []

    if source_address:
        matched.extend(prepared.get("source_address", {}).get(source_address, []))

    for card in prepared.get("raw", []):
        value = (card.get("selector") or {}).get("value")
        if value and value in raw:
            matched.append(card)

    for card in prepared.get("other", []):
        if selector_matches(card.get("selector", {}), event):
            matched.append(card)

    return matched


def find_next_context_id(bulk) -> str:
    """Choose the next tenant context with pending work, without returning tenant data."""
    if ENTERPRISE_MODE and AUTO_DISCOVER_CONTEXTS:
        row = bulk.find_next_context_with_work(
            "event_state",
            {"parsed": False},
            oldest_field="created_at",
        )
        if row and row.get("context_id"):
            return row["context_id"]
    return DEFAULT_CONTEXT_ID


def claim_context_batch(bulk, limit: int) -> Tuple[str, List[dict]]:
    """Claim a context-safe bulk batch using modules.database.mongo_bulk."""
    limit = max(1, int(limit or 1))
    context_id = find_next_context_id(bulk)
    lease_until = utcnow() + timedelta(seconds=CLAIM_LEASE_SECONDS)
    claim_patch = {
        "claimed": True,
        "claimed_by": INSTANCE_ID,
        "claimed_at": utcnow(),
        "lease_expires_at": lease_until,
    }
    claimable_filter = {
        "$or": [
            {"claimed": False},
            {"claimed": {"$exists": False}},
            {"lease_expires_at": {"$lt": utcnow()}},
        ]
    }

    states = bulk.claim_batch(
        "event_state",
        {"parsed": False},
        claim_patch,
        context_id=context_id,
        limit=limit,
        sort=[("created_at", 1), ("_id", 1)],
        claimable_filter=claimable_filter,
        claimed_by_field="claimed_by",
        include_missing_default_context=INCLUDE_MISSING_DEFAULT_CONTEXT,
    )

    if DEBUG_BATCH_CLAIMS:
        audit.log(
            event="batch_claim_debug",
            severity="INFO",
            metadata={
                "bulk_api_available": True,
                "requested_limit": limit,
                "context_id": context_id,
                "claimed_count": len(states),
            },
        )

    return context_id, states


def normalize_event_lookup_id(event_id):
    """
    event_state.event_id points to events._id in the live data model.
    This helper supports either ObjectId values or string ObjectId values.
    """
    if isinstance(event_id, ObjectId):
        return event_id

    if isinstance(event_id, str) and ObjectId.is_valid(event_id):
        return ObjectId(event_id)

    return event_id


def event_lookup_key(event_id) -> str:
    return str(event_id)


def fetch_events_bulk(bulk, event_ids: List[Any], context_id: str) -> Dict[str, dict]:
    """
    Live schema:
      event_state.event_id -> events._id

    Uses the generic context-safe bulk API.
    """
    raw_ids = [eid for eid in event_ids if eid is not None]
    lookup_ids = [normalize_event_lookup_id(eid) for eid in raw_ids]
    events = bulk.find_many_by_ids(
        "events",
        lookup_ids,
        context_id=context_id,
        id_field="_id",
        preserve_order=False,
        include_missing_default_context=False,
    )
    return {
        str(e.get("_id")): e
        for e in events
        if e.get("_id") is not None
    }


def insert_parse_results_bulk(bulk, docs: List[dict], context_id: str):
    if not docs:
        return None
    return bulk.insert_many_context(
        "parse_results",
        docs,
        context_id=context_id,
        ordered=False,
    )


def mark_states_parsed_by_state_ids(bulk, state_ids: List[Any], context_id: str):
    if not state_ids:
        return 0
    patch = {
        "parsed": True,
        "claimed": False,
        "claimed_by": "",
        "lease_expires_at": None,
        "parsed_by": INSTANCE_ID,
        "parsed_at": utcnow(),
    }
    return bulk.update_many_by_ids(
        "event_state",
        state_ids,
        patch,
        context_id=context_id,
        id_field="_id",
        include_missing_default_context=INCLUDE_MISSING_DEFAULT_CONTEXT,
    )


def mark_states_parsed_bulk(mongo, event_ids: List[Any], context_id: str):
    """
    Mark event_state rows parsed using the original event_id values from event_state.

    Do not stringify event_ids before this call. In live deployments,
    event_state.event_id may be an ObjectId. Passing stringified ObjectIds causes
    update_many({event_id: {$in: [...]}}) to match zero rows, leaving
    parsed=false forever even though the parser processed the batch.
    """
    if not event_ids:
        return 0

    patch = {
        "parsed": True,
        "claimed": False,
        "claimed_by": "",
        "lease_expires_at": None,
        "parsed_by": INSTANCE_ID,
        "parsed_at": utcnow(),
    }
    db = get_raw_db(mongo)
    if db is not None:
        query = {"event_id": {"$in": event_ids}}
        if context_id == DEFAULT_CONTEXT_ID and not ENTERPRISE_MODE:
            query["$or"] = [
                {"context_id": context_id},
                {"context_id": {"$exists": False}},
                {"context_id": None},
                {"context_id": ""},
            ]
        else:
            query["context_id"] = context_id
        res = db["event_state"].update_many(query, {"$set": patch})
        return getattr(res, "modified_count", 0)

    modified = 0
    for event_id in event_ids:
        mongo.upsert_event_state(event_id, patch, context_id=context_id)
        modified += 1
    return modified


def mark_missing_events_parsed(bulk, event_ids: List[Any], context_id: str):
    if not event_ids:
        return 0
    patch = {
        "parsed": True,
        "claimed": False,
        "claimed_by": "",
        "lease_expires_at": None,
        "parsed_by": INSTANCE_ID,
        "parsed_at": utcnow(),
        "parse_error": "event_not_found",
    }
    return bulk.update_many_by_ids(
        "event_state",
        event_ids,
        patch,
        context_id=context_id,
        id_field="event_id",
        include_missing_default_context=INCLUDE_MISSING_DEFAULT_CONTEXT,
    )


def release_claims(bulk, state_ids: List[Any], context_id: str, error: str):
    if not state_ids:
        return 0
    patch = {
        "claimed": False,
        "claimed_by": "",
        "lease_expires_at": None,
        "last_error": error,
        "last_error_at": utcnow(),
    }
    return bulk.release_batch_by_ids(
        "event_state",
        state_ids,
        patch,
        context_id=context_id,
        id_field="_id",
        include_missing_default_context=INCLUDE_MISSING_DEFAULT_CONTEXT,
    )


def event_id_for_result(event: dict) -> str:
    return str(event.get("_id") or event.get("event_id"))


def build_success_doc(event: dict, card: dict, results: dict, context_id: str) -> dict:
    return {
        "event_id": event_id_for_result(event),
        "event_object_id": event.get("_id"),
        "context_id": context_id,
        "card": safe_card_label(card),
        "results": normalize_results(results),
        "created_at": utcnow(),
    }


def build_error_doc(event: dict, card: dict, error: str, context_id: str) -> dict:
    return {
        "event_id": event_id_for_result(event),
        "event_object_id": event.get("_id"),
        "context_id": context_id,
        "card": safe_card_label(card),
        "error": str(error),
        "created_at": utcnow(),
    }


def process_batch(mongo, bulk, context_id: str, states: List[dict]):
    if not states:
        return

    # Keep original event_id values for event lookups.
    # Mark completion by event_state._id so ObjectId/string event_id mismatches
    state_ids = [s["_id"] for s in states if s.get("_id") is not None]
    raw_event_ids = [s["event_id"] for s in states if s.get("event_id") is not None]
    event_id_keys = [event_lookup_key(eid) for eid in raw_event_ids]

    events_by_id = fetch_events_bulk(bulk, raw_event_ids, context_id)

    missing_event_ids = [
        raw_event_ids[idx]
        for idx, event_id_key in enumerate(event_id_keys)
        if event_id_key not in events_by_id
    ]
    if missing_event_ids:
        mark_missing_events_parsed(bulk, missing_event_ids, context_id)
        _metrics["processed"] += len(missing_event_ids)
        _metrics["failed"] += len(missing_event_ids)

    prepared_cards = get_prepared_cards_cached(mongo, context_id)

    if DEBUG_BATCH_COUNTS:
        audit.log(
            event="batch_processing_debug",
            severity="INFO",
            metadata={
                "context_id": context_id,
                "states": len(states),
                "event_ids": len(raw_event_ids),
                "events_fetched": len(events_by_id),
                "missing_events": len(missing_event_ids),
                "cards_loaded": prepared_cards.get("total", 0),
            },
        )

    parse_docs: List[dict] = []
    extractor_jobs: List[dict] = []

    for event in events_by_id.values():
        raw_log = event.get("raw", "") or ""
        for card in matching_cards_for_event(prepared_cards, event):
            try:
                regex_results = run_regex_rules(card, raw_log)
                if regex_results:
                    parse_docs.append(build_success_doc(event, card, regex_results, context_id))
                    _metrics["matched_cards"] += 1
                elif EXTRACTOR_FALLBACK_ENABLED:
                    extractor_jobs.append({
                        "event_id": event_id_for_result(event),
                        "event": event,
                        "card": card,
                        "raw": raw_log,
                    })
            except Exception as e:
                parse_docs.append(build_error_doc(event, card, str(e), context_id))
                _metrics["failed"] += 1
        _metrics["processed"] += 1

    for job_chunk in chunks(extractor_jobs, EXTRACTOR_BATCH_SIZE):
        batch_results = call_extractor_batch_with_retry(job_chunk, context_id)
        job_by_key = {(str(j["event_id"]), safe_card_label(j["card"])): j for j in job_chunk}

        for idx, result in enumerate(batch_results):
            if not isinstance(result, dict):
                continue

            event_id = result.get("event_id")
            card_name = safe_result_card_label(result)

            if event_id is None or not card_name:
                job = job_chunk[idx] if idx < len(job_chunk) else None
            else:
                job = job_by_key.get((str(event_id), card_name)) or (job_chunk[idx] if idx < len(job_chunk) else None)

            if not job:
                continue

            event = job["event"]
            card = job["card"]

            if result.get("success") is False:
                parse_docs.append(build_error_doc(event, card, result.get("error", "extractor failed"), context_id))
                _metrics["failed"] += 1
                continue

            if "results" in result:
                fields = result["results"]
            elif "fields" in result:
                fields = result["fields"]
            else:
                parse_docs.append(build_error_doc(event, card, "Extractor response missing results/fields", context_id))
                _metrics["failed"] += 1
                continue

            if not isinstance(fields, dict):
                parse_docs.append(
                    build_error_doc(
                        event,
                        card,
                        f"Extractor returned invalid result type: {type(fields).__name__}",
                        context_id,
                    )
                )
                _metrics["failed"] += 1
                continue

            parse_docs.append(build_success_doc(event, card, fields, context_id))
            _metrics["matched_cards"] += 1

    insert_parse_results_bulk(bulk, parse_docs, context_id=context_id)
    marked_count = mark_states_parsed_by_state_ids(bulk, state_ids, context_id=context_id)

    if marked_count != len(state_ids):
        audit.log(
            event="mark_states_parsed_mismatch",
            result="warning",
            severity="WARNING",
            metadata={
                "context_id": context_id,
                "states": len(states),
                "state_ids": len(state_ids),
                "event_ids": len(raw_event_ids),
                "marked_count": marked_count,
                "hint": "Completion marking is by event_state._id; check raw DB access and context_id filter",
            },
        )

    _metrics["batches"] += 1
    _maybe_log()


def process_event(mongo, bulk, state: dict):
    context_id = resolve_context_id(state=state)
    state["context_id"] = context_id
    process_batch(mongo, bulk, context_id, [state])


def main():
    mongo = get_mongo()
    bulk = get_bulk_mongo()

    # Open once at startup so connection/auth problems fail loudly and the pool is warm.
    bulk.open_mongo_connection()

    audit.log(
        event="parser_service_started",
        metadata={
            "poll_interval": POLL_INTERVAL,
            "extractor": EXTRACTOR_SVC,
            "extractor_batch": EXTRACTOR_BATCH_SVC,
            "extractor_fallback_enabled": EXTRACTOR_FALLBACK_ENABLED,
            "batch_size": ENRICHMENT_BATCH_SIZE,
            "extractor_batch_size": EXTRACTOR_BATCH_SIZE,
            "lease_seconds": CLAIM_LEASE_SECONDS,
            "enterprise_mode": ENTERPRISE_MODE,
            "auto_discover_contexts": AUTO_DISCOVER_CONTEXTS,
            "include_missing_default_context": INCLUDE_MISSING_DEFAULT_CONTEXT,
            "bulk_api_available": True,
        },
    )

    while True:
        context_id = ""
        states: List[dict] = []

        try:
            context_id, states = claim_context_batch(bulk, ENRICHMENT_BATCH_SIZE)
            if not states:
                _maybe_log()
                time.sleep(POLL_INTERVAL)
                continue

            process_batch(mongo, bulk, context_id, states)
            # Do not sleep after successful work. Immediately claim the next batch.
            continue

        except Exception as e:
            state_ids = [s.get("_id") for s in states if s.get("_id") is not None]
            audit.log(
                event="parser_processing_failure",
                result="failure",
                severity="CRITICAL",
                metadata={"error": str(e), "context_id": context_id, "batch_size": len(states)},
            )

            if context_id and state_ids:
                try:
                    release_claims(bulk, state_ids, context_id, str(e))
                except Exception as release_error:
                    audit.log(
                        event="parser_claim_release_failed",
                        result="failure",
                        severity="ERROR",
                        metadata={"error": str(release_error), "original_error": str(e), "context_id": context_id},
                    )

            _metrics["failed"] += max(1, len(states))
            _maybe_log()
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()