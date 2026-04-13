from datetime import datetime
from time import time

from app.fetcher import fetch_one_undetected
from app.rules import load_rules
from app.analyzer import analyze_log_with_rules
from app.updater import apply_result, set_failed


_metrics = {
    "processed": 0,
    "detected": 0,
    "failed": 0,
    "last_log": 0.0,
}

_rules_cache: dict[str, list[dict]] = {}
_rules_last_load: dict[str, float] = {}
RULE_RELOAD_INTERVAL = 30


def _get_rules(context_id: str):
    now = time()

    cached_rules = _rules_cache.get(context_id)
    last_load = _rules_last_load.get(context_id, 0)

    if cached_rules is None or now - last_load > RULE_RELOAD_INTERVAL:
        _rules_cache[context_id] = load_rules(context_id)
        _rules_last_load[context_id] = now

    return _rules_cache.get(context_id, [])


def _sanitize(event: dict) -> dict:
    out = {}

    for k, v in event.items():
        if k == "_id":
            continue

        if isinstance(v, datetime):
            continue

        out[k] = v

    return out


def _maybe_log(interval: float = 5.0):
    now = time()

    if now - _metrics["last_log"] < interval:
        return

    processed = _metrics["processed"]
    rate = processed / interval if interval else 0

    print(
        f"[*] detector heartbeat "
        f"processed={processed} "
        f"detected={_metrics['detected']} "
        f"failed={_metrics['failed']} "
        f"rate={rate:.1f}/s"
    )

    _metrics["processed"] = 0
    _metrics["detected"] = 0
    _metrics["failed"] = 0
    _metrics["last_log"] = now


def process_one():
    doc = fetch_one_undetected()

    if not doc:
        _maybe_log()
        return {"status": False}

    event = doc.get("event")
    status = doc.get("status") or {}
    context_id = doc.get("context_id") or status.get("context_id") or event.get("context_id")

    if not event or not context_id:
        _metrics["failed"] += 1
        _maybe_log()
        return {"status": False}

    event_id = event.get("_id")

    if not event_id:
        _metrics["failed"] += 1
        _maybe_log()
        return {"status": False}

    to_send = _sanitize(event)
    rules = _get_rules(context_id)

    try:
        analysis = analyze_log_with_rules(to_send, rules)

        print(f"[*] analysis result detection={analysis.get('detection')}")

        rule_id = None

        for d in analysis.get("details", []):
            if d.get("matched"):
                rule_id = d.get("rule_id") or d.get("rule_name")
                break

        print(f"[*] extracted rule_id={rule_id}")

        if analysis.get("detection") and not rule_id:
            raise Exception("detection true but no rule_id found")

        apply_result(
            event_id,
            context_id,
            analysis,
            rule_id,
        )

        _metrics["processed"] += 1

        if analysis.get("detection"):
            _metrics["detected"] += 1

        _maybe_log()

        return {"status": True}

    except Exception as e:
        _metrics["processed"] += 1
        _metrics["failed"] += 1

        print(f"[✗] detector processing failed: {e}")

        set_failed(event_id, context_id, str(e))

        _maybe_log()

        return {"status": False}
