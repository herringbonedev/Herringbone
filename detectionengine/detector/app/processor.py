from datetime import datetime
from fetcher import fetch_one_undetected
from rules import load_rules
from analyzer import analyze_log_with_rules
from updater import apply_result, set_failed


def _sanitize(event: dict) -> dict:
	out = {}
	for k, v in event.items():
		if k == "_id":
			continue
		if isinstance(v, datetime):
			continue
		out[k] = v
	return out


def process_one():
	rules = load_rules()
	doc = fetch_one_undetected()

	if not doc:
		return {"status": False}

	event = doc["event"]
	event_id = event["_id"]
	to_send = _sanitize(event)

	try:
		analysis = analyze_log_with_rules(to_send, rules)
		apply_result(event_id, analysis)
		return {"status": True, "event_id": str(event_id)}
	except Exception as e:
		set_failed(event_id, str(e))
		return {"status": False, "event_id": str(event_id)}
