from datetime import datetime
from time import time
from fetcher import fetch_one_undetected
from rules import load_rules
from analyzer import analyze_log_with_rules
from updater import apply_result, set_failed


_metrics = {
	"processed": 0,
	"detected": 0,
	"failed": 0,
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
	now = time()
	if now - _metrics["last_log"] < interval:
		return

	rate = _metrics["processed"] / max(interval, 1)

	print(
		f"[*] detector heartbeat "
		f"processed={_metrics['processed']} "
		f"detected={_metrics['detected']} "
		f"failed={_metrics['failed']} "
		f"rate={rate:.1f}/s"
	)

	_metrics["processed"] = 0
	_metrics["detected"] = 0
	_metrics["failed"] = 0
	_metrics["last_log"] = now


def process_one():
	rules = load_rules()
	doc = fetch_one_undetected()

	if not doc:
		_maybe_log()
		return {"status": False}

	event = doc["event"]
	event_id = event["_id"]
	to_send = _sanitize(event)

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
			event,
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
		set_failed(event_id, str(e))

		_maybe_log()
		return {"status": False}
