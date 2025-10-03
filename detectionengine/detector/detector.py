from datetime import datetime
import os
import time
import json
import requests
import traceback

from modules.database.mongo_db import HerringboneMongoDatabase


print("Detector service has started")

def get_db(collection: str) -> HerringboneMongoDatabase:
    host = os.environ.get("MONGO_HOST", None)
    db   = os.environ.get("DB_NAME", None)
    coll = (collection or "").strip()

    print(f"[Detector] DB set -> host='{host}', db='{db}', coll='{coll}', port='{os.environ.get('MONGO_PORT', 27017)}'")

    if not host:
        raise RuntimeError("MONGO_HOST is not set")
    if not coll:
        raise RuntimeError("Collection name is not set")

    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=db,
        collection=coll,
        host=host,                               # supports FQDN, IPv4, IPv6, or host:port
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
        # no authSource (per your note)
    )

def load_rules(rules_db: HerringboneMongoDatabase) -> list[dict]:
    client, db, coll = rules_db.open_mongo_connection()
    try:
        items = list(coll.find({}))
        for r in items:
            r.pop("_id", None)
        return items
    finally:
        rules_db.close_mongo_connection()

def fetch_one_undetected(logs_db: HerringboneMongoDatabase, wait_recon: bool) -> dict | None:
    client, db, coll = logs_db.open_mongo_connection()

    try:
        query = {"$or": [{"detected": {"$exists": False}}, {"detected": False}]}

        if wait_recon:
            query["recon"] = True

        return coll.find_one(query, sort=[("_id", -1)])
    
    finally:
        logs_db.close_mongo_connection()

def set_pending(logs_db: HerringboneMongoDatabase, _id) -> None:
    logs_db.update_log({"_id": _id}, {"status": "Detection in process."}, clean_codec=False)

def set_failed(logs_db: HerringboneMongoDatabase, _id, reason: str = "") -> None:
    update = {"status": "Detection failed."}
    if reason:
        update["detection_reason"] = reason
    logs_db.update_log({"_id": _id}, update, clean_codec=False)

def set_result(logs_db: HerringboneMongoDatabase, _id, analysis: dict) -> None:
    update = {"detected": True, "updated_at": datetime.utcnow()}
    if isinstance(analysis, dict):
        if "detection" in analysis:
            update["detection"] = bool(analysis["detection"])
        if "detection_reason" in analysis:
            update["detection_reason"] = str(analysis["detection_reason"])
        if "status" in analysis and isinstance(analysis["status"], str):
            update["status"] = analysis["status"]
        else:
            update.setdefault("status", "Detection finished.")
    logs_db.update_log({"_id": _id}, update, clean_codec=False)

def write_detection_record(det_db: HerringboneMongoDatabase | None, log_id, analysis: dict) -> None:
    if not det_db:
        return
    client, db, coll = det_db.open_mongo_connection()
    try:
        coll.insert_one({"log_id": log_id, "analysis": analysis, "inserted_at": datetime.utcnow()})
    finally:
        det_db.close_mongo_connection()

def analyze(to_analyze: dict) -> dict:
    url = os.environ.get("OVERWATCH_HOST")
    if not url:
        raise RuntimeError("OVERWATCH_HOST is not set.")
    resp = requests.post(url, json=to_analyze, timeout=1000)
    print(resp.text)
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    return resp.json() if ctype.startswith("application/json") else json.loads(resp.content.decode("utf-8", "ignore"))

def main():
    rules_db = get_db(os.environ.get("RULES_COLLECTION_NAME", "rules"))
    logs_db = get_db(os.environ.get("LOGS_COLLECTION_NAME", "logs"))
    det_db = get_db(os.environ.get("DETECTIONS_COLLECTION_NAME")) if os.environ.get("DETECTIONS_COLLECTION_NAME") else None
    wait_recon = os.environ.get("WAIT_FOR_RECON_TO_FINISH", "false").lower() in "true"

    while True:
        try:
            print("[Detector] Loading rules.")
            rules = load_rules(rules_db)

            print("[Detector] Looking for undetected logs.")
            doc = fetch_one_undetected(logs_db, wait_recon)
            if not doc or "_id" not in doc:
                time.sleep(5)
                continue

            log_id = doc["_id"]
            to_send = dict(doc)
            for k in ("_id", "last_update", "last_processed", "updated_at"):
                to_send.pop(k, None)

            set_pending(logs_db, log_id)

            payload = {"log": to_send, "rules": rules}
            print(payload)
            analysis = analyze(payload)
            print("[Detector] Overwatch response parsed.")

            set_result(logs_db, log_id, analysis)
            write_detection_record(det_db, log_id, analysis)

        except Exception as e:
            print(f"[Detector] Error: {e}")
            print(traceback.format_exc())
            try:
                if "log_id" in locals():
                    set_failed(logs_db, log_id, str(e))
            except Exception as _:
                pass

        time.sleep(5)

if __name__ == "__main__":

    if os.environ.get("OVERWATCH_HOST") == "test.svc":
        print("[Test Mode] Skipping regular startup.")
        time.sleep(10)
    else:
        main()
