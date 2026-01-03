import os
from modules.database.mongo_db import HerringboneMongoDatabase


def _db(collection: str) -> HerringboneMongoDatabase:
	return HerringboneMongoDatabase(
		user=os.environ.get("MONGO_USER", ""),
		password=os.environ.get("MONGO_PASS", ""),
		database=os.environ.get("DB_NAME", ""),
		collection=collection,
		host=os.environ.get("MONGO_HOST", "localhost"),
		port=int(os.environ.get("MONGO_PORT", 27017)),
		replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
	)


def fetch_one_undetected() -> dict | None:
	status_db = _db(os.environ.get("EVENT_STATUS_COLLECTION_NAME", "event_status"))
	client, db, status_coll = status_db.open_mongo_connection()

	try:
		status = status_coll.find_one(
			{
				"parsed": True,
				"detected": False,
			},
			sort=[("_id", -1)],
		)

		if not status or "event_id" not in status:
			return None

		events_db = _db(os.environ.get("EVENTS_COLLECTION_NAME", "events"))
		e_client, e_db, events_coll = events_db.open_mongo_connection()

		try:
			event = events_coll.find_one({"_id": status["event_id"]})
			if not event:
				return None
			return {"event": event, "status": status}
		finally:
			events_db.close_mongo_connection()

	finally:
		status_db.close_mongo_connection()
