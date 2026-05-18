from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from time import time

from modules.audit.logger import AuditLogger

from app.fetcher import claim_batch_undetected, fetch_events_for_statuses, event_lookup_keys, release_claims
from app.rules import load_rules
from app.analyzer import analyze_log_with_rules
from app.updater import apply_results_bulk, set_failed


audit = AuditLogger()

_metrics = {
    "processed": 0,
    "detected": 0,
    "failed": 0,
    "missing": 0,
    "claimed": 0,
    "batches": 0,
    "last_log": 0.0,
}


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
    t = time()
    if t - _metrics["last_log"] < interval:
        return

    processed = _metrics["processed"]
    rate = processed / max(interval, 1)

    audit.log(
        event="detector_heartbeat",
        metadata={
            "processed": processed,
            "detected": _metrics["detected"],
            "failed": _metrics["failed"],
            "missing": _metrics["missing"],
            "claimed": _metrics["claimed"],
            "batches": _metrics["batches"],
            "rate_per_sec": round(rate, 2),
        },
    )

    _metrics["processed"] = 0
    _metrics["detected"] = 0
    _metrics["failed"] = 0
    _metrics["missing"] = 0
    _metrics["claimed"] = 0
    _metrics["batches"] = 0
    _metrics["last_log"] = t


def _rule_id(analysis: dict):
    for d in analysis.get("details", []):
        if d.get("matched"):
            return d.get("rule_id") or d.get("rule_name")
    return None


def _analyze_one(event: dict, status: dict, context_id: str, rules: list[dict]):
    event_id = event.get("_id")
    to_send = _sanitize(event)
    analysis = analyze_log_with_rules(to_send, rules)
    rule_id = _rule_id(analysis)

    if analysis.get("detection") and not rule_id:
        raise Exception("detection true but no rule_id found")

    return {
        "event": event,
        "status": status,
        "context_id": context_id,
        "analysis": analysis,
        "rule_id": rule_id,
        "event_id": event_id,
    }


def process_batch(batch_size: int = 100, event_workers: int = 4):
    statuses = claim_batch_undetected(batch_size)

    if not statuses:
        _maybe_log()
        return {"status": False, "processed": 0}

    _metrics["batches"] += 1
    _metrics["claimed"] += len(statuses)

    # Keep one context per batch for core/default. This is context-safe because
    # claim_batch_undetected filters by CONTEXT_ID.
    context_id = statuses[0].get("context_id") or "default"

    try:
        events_by_id = fetch_events_for_statuses(statuses, context_id)
        rules = load_rules(context_id)

        jobs = []
        missing = []

        for status in statuses:
            event = None
            for key in event_lookup_keys(status.get("event_id")):
                event = events_by_id.get(key)
                if event:
                    break

            if not event:
                missing.append(status)
                continue

            jobs.append((event, status, context_id, rules))

        results = []
        failures = []

        workers = max(1, min(int(event_workers or 1), len(jobs) or 1))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {pool.submit(_analyze_one, *job): job for job in jobs}

            for future in as_completed(future_map):
                event, status, ctx, _rules = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    failures.append((event, status, ctx, str(e)))

        if results:
            apply_results_bulk(results, context_id)
            _metrics["processed"] += len(results)
            _metrics["detected"] += sum(
                1 for r in results
                if (r.get("analysis") or {}).get("detection")
            )

        for event, status, ctx, error in failures:
            set_failed(event.get("_id"), ctx, error, status=status)
            _metrics["processed"] += 1
            _metrics["failed"] += 1

        for status in missing:
            set_failed(status.get("event_id"), context_id, "event_not_found", status=status)
            _metrics["processed"] += 1
            _metrics["failed"] += 1
            _metrics["missing"] += 1

        _maybe_log()

        return {
            "status": True,
            "processed": len(results) + len(failures) + len(missing),
            "detected": sum(1 for r in results if (r.get("analysis") or {}).get("detection")),
            "failed": len(failures) + len(missing),
            "claimed": len(statuses),
        }

    except Exception as e:
        release_claims(statuses, context_id, str(e))
        _metrics["failed"] += len(statuses)
        _maybe_log()
        raise


def process_one():
    result = process_batch(batch_size=1, event_workers=1)
    return {"status": bool(result.get("processed"))}
