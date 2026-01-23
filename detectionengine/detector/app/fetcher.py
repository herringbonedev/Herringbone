import os
from modules.database.mongo_db import HerringboneMongoDatabase


def _db() -> HerringboneMongoDatabase:
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
    )


def fetch_one_undetected() -> dict | None:
    status_collection = os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_state")
    events_collection = os.environ.get("EVENTS_COLLECTION_NAME", "events")

    mongo = _db()

    try:
        status_list = mongo.find_sorted(
            collection=status_collection,
            filter_query={
                "parsed": True,
                "detected": False,
            },
            sort=[("_id", -1)],
            limit=1,
        )
    except Exception:
        return None

    if not status_list:
        return None

    status = status_list[0]

    event_id = status.get("event_id")
    if not event_id:
        return None

    try:
        event = mongo.find_one(events_collection, {"_id": event_id})
    except Exception:
        return None

    if not event:
        return None

    return {
        "event": event,
        "status": status,
    }
