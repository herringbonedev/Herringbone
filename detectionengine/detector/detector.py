import requests
import time, os
import json
import traceback
from datetime import datetime

from modules.database.mongo_db import HerringboneMongoDatabase

print(f"""[Detector] started with the following parameters.

Overwatch endpoint: {os.environ.get("OVERWATCH_HOST")}
MongoDB Host: {os.environ.get("MONGO_HOST")}
MongoDB Database: {os.environ.get("DB_NAME")}
Rules collection: {os.environ.get("RULES_COLLECTION_NAME")}
Logs collection: {os.environ.get("LOGS_COLLECTION_NAME")}
Detections collection: {os.environ.get("DETECTIONS_COLLECTION_NAME")}
""")

def _db_for(collection_name: str) -> HerringboneMongoDatabase:
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        collection=collection_name,
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
    )

while True:
    try:
        print("[Detector] Loading rules.")
        rules_db = _db_for(os.environ.get("RULES_COLLECTION_NAME"))
        client, db, coll = rules_db.open_mongo_connection()
        try:
            rules = list(coll.find({}))
        finally:
            rules_db.close_mongo_connection()
        for rule in rules:
            rule.pop("_id", None)

        print("[Detector] Trying to find undetected logs.")
        logs_db = _db_for(os.environ.get("LOGS_COLLECTION_NAME"))
        client, db, coll = logs_db.open_mongo_connection()
        try:
            latest_not_detected = coll.find_one(
                {"$or": [{"detected": {"$exists": False}}, {"detected": False}]},
                sort=[("_id", -1)]
            )
        finally:
            logs_db.close_mongo_connection()

        log_id = latest_not_detected.get("_id") if latest_not_detected else None
        if not latest_not_detected or not log_id:
            raise Exception("No logs found to run detection.")

        latest_not_detected.pop("_id", None)
        latest_not_detected.pop("last_update", None)
        latest_not_detected.pop("last_processed", None)
        latest_not_detected.pop("updated_at", None)

        to_analyze = {"log": latest_not_detected, "rules": rules}
        print(to_analyze)

        response = requests.post(
            os.environ.get("OVERWATCH_HOST"),
            json=to_analyze,
            timeout=1000
        )
        print(response.text)
        print("Status code:", response.status_code)
        print("Content:", response.text[:500])

        analysis = response.json() if response.headers.get("content-type","").startswith("application/json") else json.loads(response.content.decode("utf-8", "ignore"))
        print(f"Storing results: {str(analysis)}")

        update_doc = {"detected": True, "updated_at": datetime.utcnow()}
        if isinstance(analysis, dict):
            if "detection" in analysis:
                update_doc["detection"] = bool(analysis["detection"])
            if "detection_reason" in analysis:
                update_doc["detection_reason"] = str(analysis["detection_reason"])

        logs_db.update_log({"_id": log_id}, update_doc, clean_codec=False)

    except Exception as e:
        print(e)
        print(traceback.format_exc())

    time.sleep(5)
