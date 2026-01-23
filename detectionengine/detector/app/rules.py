import os
from modules.database.mongo_db import HerringboneMongoDatabase


def get_rules_db() -> HerringboneMongoDatabase:
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
    )


def load_rules() -> list[dict]:
    rules_collection = os.environ.get("RULES_COLLECTION_NAME", "rules")
    mongo = get_rules_db()

    try:
        items = mongo.find(rules_collection, {})
    except Exception:
        return []

    for rule in items:
        rule.pop("_id", None)

    return items
