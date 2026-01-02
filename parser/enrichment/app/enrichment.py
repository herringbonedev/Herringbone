from datetime import datetime
import os
import time
import requests

from modules.database.mongo_db import HerringboneMongoDatabase


POLL_INTERVAL = float(os.environ.get("ENRICHMENT_POLL_INTERVAL", 1.0))
EXTRACTOR_SVC = os.environ.get("EXTRACTOR_SVC")
USE_TEST = EXTRACTOR_SVC == "test.service"

print("[*] Enrichment service has started")
if USE_TEST:
    print("[*] [Test Service] Started in test mode")


def get_mongo():
    print("[*] Initializing MongoDB connection")
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


def sanitize_card(card: dict) -> dict:
	return {
		k: (v.isoformat() if isinstance(v, datetime) else v)
		for k, v in card.items()
		if k != "_id"
	}


def selector_matches(selector: dict, event: dict) -> bool:
    stype = selector.get("type")
    value = selector.get("value")

    if stype == "source_address":
        return event.get("source", {}).get("address") == value

    if stype == "raw":
        return value in event.get("raw", "")

    return False


def call_extractor(card: dict, raw_log: str) -> dict:
    if not EXTRACTOR_SVC:
        raise RuntimeError("EXTRACTOR_SVC is not set")

    print(f"[*] Calling extractor for card '{card.get('name')}'")

    payload = {
        "card": sanitize_card(card),
        "input": raw_log,
    }

    resp = requests.post(EXTRACTOR_SVC, json=payload, timeout=30)
    resp.raise_for_status()

    print("[✓] Extractor call succeeded")
    return resp.json()


def main():
    mongo = get_mongo()
    print("[✓] Connected to MongoDB")

    while True:
        print("[*] Polling for unparsed event_state")

        state = mongo.find_one(
            "event_state",
            {"parsed": False},
        )

        if not state:
            print("[x] No unparsed event_state found")
            time.sleep(POLL_INTERVAL)
            continue

        print(f"[*] Found event_state for event {state.get('event_id')}")

        event = mongo.find_one(
            "events",
            {"_id": state["event_id"]},
        )

        if not event:
            print("[x] Event not found, marking state as parsed")
            mongo.upsert_event_state(
                state["event_id"],
                {"parsed": True},
            )
            continue

        print(f"[*] Processing event {event.get('_id')}")
        print(f"[*] Event keys: {list(event.keys())}")

        cards = mongo.find("parse_cards", {})
        print("[*] Loaded parse cards")

        for card in cards:
            print(f"[*] Evaluating card '{card.get('name')}'")

            if not selector_matches(card.get("selector", {}), event):
                print("[x] Selector did not match, skipping card")
                continue

            print("[*] Selector matched, running extractor")

            try:
                result = call_extractor(card, event.get("raw", ""))

                mongo.insert_parse_result(
                    {
                        "event_id": event["_id"],
                        "card": card.get("name"),
                        "results": result,
                        "created_at": datetime.utcnow(),
                    }
                )

                print("[✓] Parse result inserted")

            except Exception as e:
                print("[x] Extractor failed:", e)

                mongo.insert_parse_result(
                    {
                        "event_id": event["_id"],
                        "card": card.get("name"),
                        "error": str(e),
                        "created_at": datetime.utcnow(),
                    }
                )

        print("[*] Marking event as parsed")

        mongo.upsert_event_state(
            event["_id"],
            {
                "parsed": True,
            },
        )

        print("[✓] Event marked as parsed")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
