import os
import requests
from datetime import datetime, timezone
from typing import Any

from app.dbutil import mongo_db, mongo_bulk


ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", None)
SERVICE_TOKEN_PATH = "/run/secrets/service_token"
INCLUDE_MISSING_DEFAULT_CONTEXT = os.environ.get("INCLUDE_MISSING_DEFAULT_CONTEXT", "false").lower() == "true"
NOTIFY_ORCHESTRATOR = os.environ.get("DETECTOR_NOTIFY_ORCHESTRATOR", "true").lower() == "true"
WRITE_DETECTIONS = os.environ.get("DETECTOR_WRITE_DETECTIONS", "true").lower() == "true"
_SERVICE_TOKEN_CACHE = None


def utcnow():
    return datetime.now(timezone.utc)


def service_auth_headers():
    global _SERVICE_TOKEN_CACHE

    if _SERVICE_TOKEN_CACHE is not None:
        return {"Authorization": f"Bearer {_SERVICE_TOKEN_CACHE}"}

    try:
        with open(SERVICE_TOKEN_PATH, "r") as f:
            _SERVICE_TOKEN_CACHE = f.read().strip()
        return {"Authorization": f"Bearer {_SERVICE_TOKEN_CACHE}"}
    except Exception as e:
        print(f"[✗] Failed to read service token: {e}")
        return {}


def service_headers(context_id: str):
    return {
        **service_auth_headers(),
        "X-Herringbone-Context": context_id,
    }


def _max_severity(analysis: dict):
    vals = [
        int(d["severity"])
        for d in analysis.get("details", [])
        if d.get("matched") and d.get("severity") is not None
    ]
    return max(vals) if vals else None


def _correlate_values(analysis: dict):
    values = []
    for d in analysis.get("details", []):
        if d.get("matched") and d.get("correlate_on"):
            values.extend(d.get("correlate_on") or [])
    return values


def notify_orchestrator(payload: dict, context_id: str):
    if not NOTIFY_ORCHESTRATOR or not ORCHESTRATOR_URL:
        return

    if not context_id:
        print("[✗] Missing context_id, skipping orchestrator notification")
        return

    try:
        resp = requests.post(
            ORCHESTRATOR_URL,
            json={**payload, "context_id": context_id},
            headers=service_headers(context_id),
            timeout=2,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[✗] Failed to notify orchestrator: {e}")


def _status_patch(analysis: dict, now):
    severity = _max_severity(analysis)
    patch = {
        "detected": True,
        "detection": bool(analysis.get("detection")),
        "analysis": analysis,
        "last_stage": "detector",
        "correlate_on": _correlate_values(analysis),
        "last_updated": now,
        "detection_claimed": False,
        "detection_claimed_by": "",
        "detection_lease_expires_at": None,
    }
    if severity is not None:
        patch["severity"] = severity
    return patch


def _update_status_exact(status: dict, analysis: dict, context_id: str, now):
    status_collection = os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state")
    status_id = (status or {}).get("_id")

    if status_id is None:
        print("[✗] Missing event_state _id, refusing unsafe detector status update")
        return 0

    patch = _status_patch(analysis, now)

    try:
        bulk = mongo_bulk()
        return bulk.update_many_by_ids(
            status_collection,
            [status_id],
            patch,
            context_id=context_id,
            id_field="_id",
            include_missing_default_context=INCLUDE_MISSING_DEFAULT_CONTEXT,
        ) or 0
    except Exception as e:
        print(f"[WARN] detector bulk status update unavailable, using wrapper fallback: {e}")
        mongo = mongo_db()
        try:
            if hasattr(mongo, "update_one"):
                mongo.update_one(status_collection, {"_id": status_id}, {"$set": patch}, context_id=context_id)
            else:
                # Last resort: old wrapper only. This is less ideal, but keeps old deployments alive.
                mongo.upsert_one(status_collection, {"_id": status_id}, patch, context_id=context_id)
            return 1
        except Exception as err:
            print(f"[✗] Failed to update detector status: {err}")
            return 0


def _insert_detection_docs(docs: list[dict], context_id: str):
    det_collection = os.environ.get("DETECTIONS_COLLECTION_NAME")
    if not det_collection or not docs or not WRITE_DETECTIONS:
        return 0

    try:
        bulk = mongo_bulk()
        bulk.insert_many_context(det_collection, docs, context_id=context_id, ordered=False)
        return len(docs)
    except Exception as e:
        print(f"[WARN] detector bulk detection insert unavailable, using wrapper fallback: {e}")
        mongo = mongo_db()
        inserted = 0
        for doc in docs:
            try:
                mongo.insert_one(det_collection, doc, context_id=context_id, clean_codec=False)
                inserted += 1
            except Exception as err:
                print(f"[✗] Failed to write detection record: {err}")
        return inserted


def apply_results_bulk(items: list[dict], context_id: str):
    now = utcnow()
    updated = 0
    detection_docs = []
    notifications = []

    for item in items:
        event = item.get("event") or {}
        status = item.get("status") or {}
        analysis = item.get("analysis") or {"detection": False, "details": []}
        rule_id = item.get("rule_id")
        event_id = event.get("_id") or status.get("event_id")
        severity = _max_severity(analysis)
        detected = bool(analysis.get("detection"))
        correlate_values = _correlate_values(analysis)

        updated += _update_status_exact(status, analysis, context_id, now)

        if not detected:
            continue

        notifications.append(
            {
                "detection_id": str(event_id),
                "rule_id": rule_id,
                "event_ids": [str(event_id)],
                "severity": severity,
                "correlate_on": correlate_values,
                "priority": "high" if (severity or 0) >= 75 else "medium",
                "timestamp": now.isoformat(),
            }
        )

        detection_docs.append(
            {
                "event_id": str(event_id),
                "event_object_id": event.get("_id"),
                "rule_id": rule_id,
                "detection": True,
                "severity": severity,
                "analysis": analysis,
                "inserted_at": now,
                "context_id": context_id,
            }
        )

    inserted = _insert_detection_docs(detection_docs, context_id)

    for payload in notifications:
        notify_orchestrator(payload, context_id)

    return {"updated": updated, "detections": inserted}


def set_failed(event_id, context_id: str, reason: str, status: dict | None = None):
    status = status or {}
    analysis = {
        "detection": False,
        "details": [],
        "error": reason,
    }
    return apply_results_bulk(
        [{"event": {"_id": event_id}, "status": status, "analysis": analysis, "rule_id": None}],
        context_id,
    )


def apply_result(event_id, context_id: str, analysis: dict, rule_id: str, status: dict | None = None):
    return apply_results_bulk(
        [{"event": {"_id": event_id}, "status": status or {}, "analysis": analysis, "rule_id": rule_id}],
        context_id,
    )
