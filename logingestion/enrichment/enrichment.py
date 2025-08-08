from pymongo import MongoClient, ReturnDocument
from datetime import datetime
import time
import os
import requests

print("Enrichment service has started")

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

class MongoNotSet(Exception):
    """If the MONGO_HOST is not set in the container environment variables"""
    pass

MONGO_HOST = os.environ.get('MONGO_HOST', None)
DB_NAME = os.environ.get("DB_NAME")
COLLECTION_NAME = os.environ.get('COLLECTION_NAME')
MONGO_USER = os.environ.get('MONGO_USER')
MONGO_PASS = os.environ.get('MONGO_PASS')
AUTH_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}/{DB_NAME}"

if MONGO_HOST is not None:
    client = MongoClient(MONGO_HOST)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

else:
    raise MongoNotSet("MONGO_HOST is not set in the container environment variables.")

try:
    client = MongoClient(AUTH_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

except Exception as e:
    raise Exception(f"Failed to connect to MongoDB: {e}")

while True:

    print(AUTH_URI)

    doc = collection.find_one({
        "recon": False,
        "recon_data": None,
    })

    if not doc:
        time.sleep(1)
        continue

    try:
        enrichment_result = perform_recon(doc["raw_log"])
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
        collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"recon": False}}
        )
        print(f"[✗] Failed to enrich log {doc['_id']}: {e}")