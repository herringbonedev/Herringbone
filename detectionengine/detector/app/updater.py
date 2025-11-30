import os
from datetime import datetime
from modules.database.mongo_db import HerringboneMongoDatabase


def get_logs_db() -> HerringboneMongoDatabase:
    """Return DB instance for logs."""
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", ""),
        collection=os.environ.get("LOGS_COLLECTION_NAME", "logs"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
    )


def get_detections_db() -> HerringboneMongoDatabase | None:
    """Return DB instance for detections, or None if disabled."""
    coll = os.environ.get("DETECTIONS_COLLECTION_NAME")
    if not coll:
        return None

    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", ""),
        collection=coll,
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
    )


def set_failed(log_id, reason: str = ""):
    """Mark a log as failed detection."""
    update = {"detected": True,"detection_results": {"status": "Detection failed."}}
    if reason:
        update["detection_results"]["detection_reason"] = reason

    db = get_logs_db()
    print(f"[*] Updating logs collection with {str(update)}")
    db.update_log({"_id": log_id}, update, clean_codec=False)


def apply_result(log_id, analysis: dict):
    """Apply detection result and optionally store record."""
    update = {
        "detected": True,
        "detection_results": {
            "updated_at": datetime.utcnow(),
        }
    }

    if isinstance(analysis, dict):
        if "detection" in analysis:
            update["detection_results"]["detection"] = bool(analysis["detection"])
        if "detection_reason" in analysis:
            update["detection_results"]["detection_reason"] = str(analysis["detection_reason"])
        if "status" in analysis:
            update["detection_results"]["status"] = analysis["status"]
        else:
            update["detection_results"].setdefault("status", "Detection finished.")

    logs_db = get_logs_db()
    print(f"[*] Updating logs collection with {str(update)}")
    logs_db.update_log({"_id": log_id}, update, clean_codec=False)

    det_db = get_detections_db()
    if det_db:
        det_db.insert_log(
            {"log_id": log_id, "analysis": analysis, "inserted_at": datetime.utcnow()},
            clean_codec=False,
        )
