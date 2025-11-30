from modules.database.mongo_db import HerringboneMongoDatabase
import os


def get_rules_db() -> HerringboneMongoDatabase:
    """Returns a DB instance configured for the rules collection."""
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", ""),
        collection=os.environ.get("RULES_COLLECTION_NAME", "rules"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
    )


def load_rules() -> list[dict]:
    """
    Loads all detection rules from the rules collection.
    Removes the Mongo _id field before returning.
    """
    rules_db = get_rules_db()
    client, db, coll = rules_db.open_mongo_connection()

    try:
        items = list(coll.find({}))
        for rule in items:
            rule.pop("_id", None)
        return items

    finally:
        rules_db.close_mongo_connection()
