from datetime import datetime, timezone
import os
import time
import requests
import socket
from time import time as now

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.audit.logger import AuditLogger


POLL_INTERVAL = float(os.environ.get("ENRICHMENT_POLL_INTERVAL", 0.01))
CARD_CACHE_SECONDS = float(os.environ.get("CARD_CACHE_SECONDS", 30.0))
EXTRACTOR_SVC = os.environ.get("EXTRACTOR_SVC")
USE_TEST = EXTRACTOR_SVC == "test.service"

SERVICE_TOKEN_PATH = "/run/secrets/service_token"
INSTANCE_ID = socket.gethostname()

audit = AuditLogger()

_metrics = {
    "processed": 0,
    "matched_cards": 0,
    "failed": 0,
    "last_log": 0.0,
}

_card_cache = {
    "context_id": None,
    "cards": [],
    "loaded_at": 0.0,
}

print("[*] Enrichment service has started")

if USE_TEST:
    print("[*] [Test Service] Started in test mode")


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
            "rate_per_sec": round(rate, 2),
        },
    )

    _metrics["processed"] = 0
    _metrics["matched_cards"] = 0
    _metrics["failed"] = 0
    _metrics["last_log"] = t


def service_auth_headers(context_id: str):
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


def sanitize_card(card: dict) -> dict:
    return {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in card.items()
        if k != "_id"
    }


def selector_matches(selector: dict, event: dict) -> bool:
    stype = selector.get("type")
    value = selector.get("value")

    if stype == "source_address":
        return event.get("source", {}).get("address") == value

    if stype == "raw":
        return value in event.get("raw", "")

    return False


def call_extractor(card: dict, raw_log: str, context_id: str) -> dict:
    if not EXTRACTOR_SVC:
        raise RuntimeError("EXTRACTOR_SVC is not set")

    payload = {
        "card": sanitize_card(card),
        "input": raw_log,
    }

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


def get_cards_cached(mongo, context_id: str):
    t = now()

    if (
        _card_cache["context_id"] == context_id
        and _card_cache["cards"]
        and t - _card_cache["loaded_at"] < CARD_CACHE_SECONDS
    ):
        return _card_cache["cards"]

    cards = mongo.find_with_context(
        "parse_cards",
        {},
        context_id=context_id,
    )

    _card_cache["context_id"] = context_id
    _card_cache["cards"] = cards
    _card_cache["loaded_at"] = t

    return cards


def normalize_results(results: dict) -> dict:
    normalized = {}
    for k, v in results.items():
        normalized[k] = v if isinstance(v, list) else [v]
    return normalized


def process_event(mongo, state: dict):

    context_id = state.get("context_id")

    if not context_id:
        audit.log(
            event="missing_context_in_state",
            severity="CRITICAL",
            metadata={"state": state},
        )
        return

    audit.log(
        event="processing_event",
        metadata={
            "event_id": str(state.get("event_id")),
            "context_id": context_id,
        },
    )

    event = mongo.find_one_with_context(
        "events",
        {"_id": state["event_id"]},
        context_id=context_id,
    )

    if not event:
        mongo.upsert_event_state(
            state["event_id"],
            {"parsed": True},
            context_id=context_id,
        )

        _metrics["processed"] += 1
        _metrics["failed"] += 1
        _maybe_log()
        return

    cards = get_cards_cached(mongo, context_id)

    for card in cards:

        if not selector_matches(card.get("selector", {}), event):
            continue

        try:

            results = {}

            regex_rules = card.get("regex") or []

            for rule in regex_rules:
                if "pattern" in rule and "name" in rule:
                    import re
                    m = re.search(rule["pattern"], event.get("raw", ""))
                    if m:
                        results[rule["name"]] = [m.group(0)]

            if not results:

                raw_result = call_extractor(card, event.get("raw", ""), context_id)

                if not isinstance(raw_result, dict):
                    raise RuntimeError("Extractor returned invalid result shape")

                results = normalize_results(raw_result)

            mongo.insert_parse_result(
                {
                    "event_id": event["_id"],
                    "card": card.get("name"),
                    "results": results,
                    "created_at": datetime.now(timezone.utc),
                },
                context_id=context_id,
            )

            _metrics["processed"] += 1
            _metrics["matched_cards"] += 1

        except Exception as e:

            mongo.insert_parse_result(
                {
                    "event_id": event["_id"],
                    "card": card.get("name"),
                    "error": str(e),
                    "created_at": datetime.now(timezone.utc),
                },
                context_id=context_id,
            )

            audit.log(
                event="parser_card_failed",
                result="failure",
                severity="ERROR",
                target=card.get("name"),
                metadata={
                    "event_id": str(event["_id"]),
                    "context_id": context_id,
                    "error": str(e),
                },
            )

            _metrics["processed"] += 1
            _metrics["failed"] += 1

    mongo.upsert_event_state(
        event["_id"],
        {"parsed": True, "claimed": False, "claimed_by":"", "parsed_by": INSTANCE_ID},
        context_id=context_id,
    )

    _maybe_log()


def main():

    mongo = get_mongo()

    audit.log(
        event="parser_service_started",
        metadata={
            "poll_interval": POLL_INTERVAL,
            "extractor": EXTRACTOR_SVC,
        },
    )

    while True:

        state = mongo.find_one("event_state", {"parsed": False, "claimed": False})

        if not state:
            _maybe_log()
            time.sleep(POLL_INTERVAL)
            continue

        try:
            mongo.upsert_event_state(
                state["event_id"],
                {"claimed": True, "claimed_by": INSTANCE_ID},
                context_id=state["context_id"],
            )
            process_event(mongo, state)
        except Exception as e:

            audit.log(
                event="parser_processing_failure",
                result="failure",
                severity="CRITICAL",
                metadata={"error": str(e)},
            )

            _metrics["failed"] += 1
            _maybe_log()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()