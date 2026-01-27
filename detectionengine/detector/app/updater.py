import os
import requests
from datetime import datetime
from modules.database.mongo_db import HerringboneMongoDatabase


ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", None)
SERVICE_TOKEN_PATH = "/run/secrets/service_token"


def service_auth_headers():
    try:
        with open(SERVICE_TOKEN_PATH, "r") as f:
            token = f.read().strip()
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"[✗] Failed to read service token: {e}")
        return {}


def _db() -> HerringboneMongoDatabase:
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
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
        resp = requests.post(ORCHESTRATOR_URL, 
                             json=payload, 
                             headers=service_auth_headers(), 
                             timeout=2)
        
        resp.raise_for_status()
        print("[✓] Detection forwarded to orchestrator")
    except Exception as e:
        print(f"[✗] Failed to notify orchestrator: {e}")


def set_failed(event_id, reason: str):
    now = datetime.utcnow()
    mongo = _db()

    status_collection = os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state")

    try:
        mongo.upsert_one(
            status_collection,
            {"event_id": event_id},
            {
                "detected": True,
                "detection": False,
                "last_stage": "detector",
                "last_updated": now,
                "error": reason,
            },
        )
    except Exception as e:
        print(f"[✗] Failed to mark event failed: {e}")


def apply_result(event_id, analysis: dict, rule_id: str):
    now = datetime.utcnow()
    severity = _max_severity(analysis)
    detected = bool(analysis.get("detection"))

    mongo = _db()
    status_collection = os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state")

    correlate_values = []

    for d in analysis.get("details", []):
        if d.get("matched") and d.get("correlate_on"):
            correlate_values.extend(d.get("correlate_on"))

    update_fields = {
        "detected": True,
        "detection": detected,
        "analysis": analysis,
        "last_stage": "detector",
        "correlate_on": correlate_values,
        "last_updated": now,
    }

    if severity is not None:
        update_fields["severity"] = severity

    try:
        mongo.upsert_one(
            status_collection,
            {"event_id": event_id},
            update_fields,
        )
    except Exception as e:
        print(f"[✗] Failed to update status: {e}")
        return

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

    det_collection = os.environ.get("DETECTIONS_COLLECTION_NAME")
    if det_collection:
        try:
            mongo.insert_one(
                det_collection,
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
        except Exception as e:
            print(f"[✗] Failed to write detection record: {e}")
