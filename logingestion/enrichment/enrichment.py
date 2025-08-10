from pymongo import MongoClient, ReturnDocument
from datetime import datetime
import time
import os
import requests

class MongoNotSet(Exception):
    """If the MONGO_HOST is not set in the container environment variables"""
    pass

print("Enrichment service has started")
if os.environ.get("ENRICHMENT_SVC") == "test.service":
    print("[Test Service] Started in test mode")

def perform_recon(raw_log):
    url = os.environ.get("ENRICHMENT_SVC")

    if url == "test.service":
        print("[Test Service]")
        return {"pass": True}
    
    payload = {"record": raw_log}

    try:
        response = requests.post(url, json=payload, timeout=1000)
        print(response.text)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Enrichment service failed: {e}")

MONGO_HOST = os.environ.get('MONGO_HOST', None)
DB_NAME = os.environ.get("DB_NAME", None)
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', None)
MONGO_USER = os.environ.get('MONGO_USER', None)
MONGO_PASS = os.environ.get('MONGO_PASS', None)

if MONGO_HOST is not None:
    client = MongoClient(MONGO_HOST)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    AUTH_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}/{DB_NAME}"

    try:
        client = MongoClient(AUTH_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

    except Exception as e:
        raise Exception(f"Failed to connect to MongoDB: {e}")
    
elif os.environ.get("ENRICHMENT_SVC") == "test.service":
    print("[Test Mode] Ignoring MongoDB connection.")

else:
    raise MongoNotSet("MONGO_HOST is not set in the container environment variables.")

while True:

    if os.environ.get("ENRICHMENT_SVC") == "test.service":
        print("[Test Mode] Using test log")
        doc = {
        "timestamp": "00:00:00",
        "raw_log": "Test log message",
        "source": "github-actions",
        "recon": False,
        "recon_data": None
      }
    else:
        doc = collection.find_one({
            "recon": False,
            "recon_data": None,
        })

    if not doc:
        time.sleep(1)
        continue

    try:
        enrichment_result = perform_recon(doc["raw_log"])
        if os.environ.get("ENRICHMENT_SVC") != "test.svc":
            collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "recon": True,
                        "recon_data": enrichment_result,
                        "last_processed": datetime.utcnow()
                    }
                }
            )
            print(f"[✓] Enriched log {doc['_id']}")
    except Exception as e:
        if os.environ.get("ENRICHMENT_SVC") != "test.svc":
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"recon": False}}
            )
        print(f"[✗] Failed to enrich log {doc['_id']}: {e}")