import os
import requests
from datetime import datetime
from modules.database.mongo_db import HerringboneMongoDatabase

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", None)


def _db(collection: str) -> HerringboneMongoDatabase:
	return HerringboneMongoDatabase(
		user=os.environ.get("MONGO_USER", ""),
		password=os.environ.get("MONGO_PASS", ""),
		database=os.environ.get("DB_NAME", ""),
		collection=collection,
		host=os.environ.get("MONGO_HOST", "localhost"),
		port=int(os.environ.get("MONGO_PORT", 27017)),
		replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
	)


def _max_severity(analysis: dict):
	vals = [
		int(d["severity"])
		for d in analysis.get("details", [])
		if d.get("matched") and d.get("severity") is not None
	]
	return max(vals) if vals else None


def notify_orchestrator(payload):
	if not ORCHESTRATOR_URL:
		print("[✗] ORCHESTRATOR_URL not set, skipping notification")
		return

	try:
		resp = requests.post(ORCHESTRATOR_URL, json=payload, timeout=2)
		resp.raise_for_status()
		print("[✓] Detection forwarded to orchestrator")
	except Exception as e:
		print(f"[✗] Failed to notify orchestrator: {e}")


def set_failed(event_id, reason: str):
	now = datetime.utcnow()
	status_db = _db(os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state"))
	client, db, coll = status_db.open_mongo_connection()

	try:
		coll.update_one(
			{"event_id": event_id},
			{
				"$set": {
					"detected": True,
					"detection": False,
					"last_stage": "detector",
					"last_updated": now,
					"error": reason,
				}
			},
			upsert=True,
		)
	finally:
		status_db.close_mongo_connection()


def apply_result(event_id, analysis: dict, rule_id: str):
	now = datetime.utcnow()
	severity = _max_severity(analysis)
	detected = bool(analysis.get("detection"))

	status_db = _db(os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state"))
	client, db, coll = status_db.open_mongo_connection()

	correlate_values = []

	for d in analysis.get("details", []):
		if d.get("matched") and d.get("correlate_on"):
			correlate_values.append(d.get("correlate_on"))
	
	try:
		update = {
			"$set": {
				"detected": True,
				"detection": detected,
				"analysis": analysis,
				"last_stage": "detector",
				"correlate_on": correlate_values,
				"last_updated": now,
			}
		}
		if severity is not None:
			update["$set"]["severity"] = severity

		coll.update_one({"event_id": event_id}, update, upsert=True)

	finally:
		status_db.close_mongo_connection()

	if detected:
		print("[*] Detection evaluated as TRUE")
		notify_orchestrator({
			"detection_id": str(event_id),
			"rule_id": rule_id,
			"event_ids": [str(event_id)],
			"severity": severity,
			"correlate_on": correlate_values,
			"priority": "high" if (severity or 0) >= 75 else "medium",
			"timestamp": now.isoformat(),
		})

	det_coll = os.environ.get("DETECTIONS_COLLECTION_NAME")
	if det_coll:
		det_db = _db(det_coll)
		det_db.insert_log(
			{
				"event_id": event_id,
				"detection": detected,
				"severity": severity,
				"analysis": analysis,
				"inserted_at": now,
			},
			clean_codec=False,
		)
		print("[✓] Detection written to detections collection")
