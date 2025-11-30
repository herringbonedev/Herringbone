from modules.database.mongo_db import HerringboneMongoDatabase
import os


def get_logs_db() -> HerringboneMongoDatabase:
    """Return a DB instance configured for the logs collection."""
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", ""),
        collection=os.environ.get("LOGS_COLLECTION_NAME", "logs"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
    )


def fetch_one_undetected(wait_recon: bool = False) -> dict | None:
    """
    Get a single log document that hasn't been detected yet.
    If wait_recon=True then require recon=True as well.
    """
    logs_db = get_logs_db()
    client, db, coll = logs_db.open_mongo_connection()

    try:
        query = {
            "$or": [
                {"detection_results.detected": {"$exists": False}},
                {"detection_results.detected": False},
            ]
        }

        if wait_recon:
            query["recon"] = True

        doc = coll.find_one(query, sort=[("_id", -1)])
        return doc

    finally:
        logs_db.close_mongo_connection()
