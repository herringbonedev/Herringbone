from datetime import datetime
from fetcher import fetch_one_undetected
from rules import load_rules
from analyzer import analyze_log_with_rules
from updater import set_pending, apply_result, set_failed


def process_one():
    """Runs one detection cycle."""
    rules = load_rules()
    doc = fetch_one_undetected()

    if not doc or "_id" not in doc:
        return {"status": False, "msg": "no_logs"}

    log_id = doc["_id"]

    to_send = {}
    for key, value in doc.items():
        if key in ("_id", "last_update", "last_processed", "updated_at"):
            continue
        if isinstance(value, datetime):
            continue
        to_send[key] = value

    set_pending(log_id)

    try:
        analysis = analyze_log_with_rules(to_send, rules)
        apply_result(log_id, analysis)
        return {"status": True, "log_id": str(log_id), "analysis": analysis}
    except Exception as e:
        set_failed(log_id, str(e))
        return {"status": False, "log_id": str(log_id), "error": str(e)}
