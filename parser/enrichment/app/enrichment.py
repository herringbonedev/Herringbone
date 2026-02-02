from datetime import datetime, UTC
import os
import time
import requests

from modules.database.mongo_db import HerringboneMongoDatabase


POLL_INTERVAL = float(os.environ.get("ENRICHMENT_POLL_INTERVAL", 1.0))
EXTRACTOR_SVC = os.environ.get("EXTRACTOR_SVC")
USE_TEST = EXTRACTOR_SVC == "test.service"

SERVICE_TOKEN_PATH = "/run/secrets/service_token"

print("[*] Enrichment service has started")
if USE_TEST:
    print("[*] [Test Service] Started in test mode")


def service_auth_headers():
    with open(SERVICE_TOKEN_PATH, "r") as f:
        token = f.read().strip()
    return {"Authorization": f"Bearer {token}"}


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

    resp = requests.post(
        EXTRACTOR_SVC,
        json=payload,
        headers=service_auth_headers(),
        timeout=30,
    )
    resp.raise_for_status()

    data = resp.json()

    print("[✓] Extractor call succeeded")
    print(data)

    if isinstance(data, dict) and "results" in data and isinstance(data["results"], dict):
        return data["results"]

    if not isinstance(data, dict):
        raise RuntimeError("Extractor returned invalid result shape")

    return data


def process_event(mongo, state):
    event = mongo.find_one("events", {"_id": state["event_id"]})

    if not event:
        mongo.upsert_event_state(state["event_id"], {"parsed": True})
        return

    cards = mongo.find("parse_cards", {})

    for card in cards:
        if not selector_matches(card.get("selector", {}), event):
            continue

        try:
            result = call_extractor(card, event.get("raw", ""))

            if not isinstance(result, dict):
                raise RuntimeError("Extractor returned invalid result shape")

            for v in result.values():
                if not isinstance(v, list):
                    raise RuntimeError("Extractor returned invalid result shape")

            mongo.insert_parse_result({
                "event_id": event["_id"],
                "card": card.get("name"),
                "results": result,
                "created_at": datetime.now(UTC),
            })

        except Exception as e:
            mongo.insert_parse_result({
                "event_id": event["_id"],
                "card": card.get("name"),
                "error": str(e),
                "created_at": datetime.now(UTC),
            })

    mongo.upsert_event_state(event["_id"], {"parsed": True})


def process_once(mongo) -> bool:
    state = mongo.find_one("event_state", {"parsed": False})

    if not state:
        return False  # nothing processed

    process_event(mongo, state)
    return True


def main():
    mongo = get_mongo()
    print("[✓] Connected to MongoDB")

    while True:
        print("[*] Polling for unparsed event_state")

        processed = process_once(mongo)

        if not processed:
            print("[x] No unparsed event_state found")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
