from datetime import datetime
import os
import time
import requests

from modules.database.mongo_db import HerringboneMongoDatabase


class MongoNotSet(Exception):
    """Raised when required Mongo env vars are missing (non-test mode)."""
    pass


print("Enrichment service has started")
USE_TEST = os.environ.get("ENRICHMENT_SVC") == "test.service"
if USE_TEST:
    print("[Test Service] Started in test mode")


def perform_recon(raw_log: str) -> dict:
    """
    Call the enrichment endpoint with the raw log.
    Honors test mode when ENRICHMENT_SVC == 'test.service'.
    """
    url = os.environ.get("ENRICHMENT_SVC")

    if url == "test.service":
        print("[Test Service] Using mock enrichment")
        return {"pass": True}

    payload = {"record": raw_log}
    try:
        response = requests.post(url, json=payload, timeout=1000)
        print(response.text)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Enrichment service failed: {e}")


def get_mongo() -> HerringboneMongoDatabase | None:
    """
    Construct the DB helper from env. Returns None in test mode.
    The helper safely handles credentials, IPv6 hosts, and host:port strings.
    """
    if USE_TEST:
        return None

    mongo_host = os.environ.get("MONGO_HOST")
    db_name = os.environ.get("DB_NAME")
    coll_name = os.environ.get("COLLECTION_NAME")
    mongo_user = os.environ.get("MONGO_USER", "")
    mongo_pass = os.environ.get("MONGO_PASS", "")
    mongo_port = int(os.environ.get("MONGO_PORT", 27017))
    auth_source = os.environ.get("MONGO_AUTH_SOURCE", "admin")
    replica_set = os.environ.get("MONGO_REPLICA_SET") or None

    if not mongo_host or not db_name or not coll_name:
        raise MongoNotSet("MONGO_HOST, DB_NAME, and COLLECTION_NAME must be set.")

    return HerringboneMongoDatabase(
        user=mongo_user,
        password=mongo_pass,
        database=db_name,
        collection=coll_name,
        host=mongo_host,
        port=mongo_port,
        auth_source=auth_source,
        replica_set=replica_set,
    )


def fetch_one_pending(mongo: HerringboneMongoDatabase) -> dict | None:
    """
    Fetch a single document pending recon: recon == False and recon_data == None.
    Uses the module's connection lifecycle.
    """
    client, db, coll = mongo.open_mongo_connection()
    try:
        return coll.find_one({"recon": False, "recon_data": None})
    finally:
        mongo.close_mongo_connection()


def set_enriched(
    mongo: HerringboneMongoDatabase,
    _id,
    enrichment_result: dict,
) -> None:
    """
    Mark a doc as enriched using the module's update helper.
    """
    mongo.update_log(
        {"_id": _id},
        {
            "recon": True,
            "recon_data": enrichment_result,
            "status": "Recon finished."
            "last_processed": datetime.utcnow(),
        },
        clean_codec=False,
    )


def set_failed(mongo: HerringboneMongoDatabase, _id) -> None:
    """
    Mark a doc as failed (recon False) using the module's update helper.
    """
    mongo.update_log(
        {"_id": _id},
        {"recon": False,
         "status": "Recon failed."},
        clean_codec=False,
    )

def set_pending(mongo: HerringboneMongoDatabase, _id) -> None:
    """
    Mark a doc with pending status using the module's update helper.
    """
    mongo.update_log(
        {"_id": _id},
        {"status": "Recon in process."},
        clean_codec=False,
    )


def main():
    mongo = get_mongo()  # None in test mode

    while True:
        # Build a test doc or fetch from Mongo
        if USE_TEST:
            print("[Test Mode] Using test log")
            doc = {
                "timestamp": "00:00:00",
                "raw_log": "Test log message",
                "source": "github-actions",
                "recon": False,
                "recon_data": None,
            }
        else:
            try:
                doc = fetch_one_pending(mongo)
            except Exception as e:
                print(f"[✗] Mongo fetch failed: {e}")
                time.sleep(1)
                continue

        if not doc:
            time.sleep(1)
            continue

        try:
            set_pending(mongo, doc["_id"])
            enrichment_result = perform_recon(doc["raw_log"])
            if not USE_TEST:
                print("[→] Updating enriched log in MongoDB")
                set_enriched(mongo, doc["_id"], enrichment_result)
                print(f"[✓] Enriched log {doc['_id']}")
        except Exception as e:
            if not USE_TEST and "_id" in doc:
                print("[→] Marking log as not enriched in MongoDB")
                try:
                    set_failed(mongo, doc["_id"])
                except Exception as e2:
                    print(f"[✗] Failed to update failure state for {doc['_id']}: {e2}")
            print(f"[✗] Failed to enrich log {doc.get('_id', 'test_doc')}: {e}")


if __name__ == "__main__":
    main()
