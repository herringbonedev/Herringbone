from flask import Flask, request
from datetime import datetime, UTC
import os
import socket

from modules.database.mongo_db import HerringboneMongoDatabase
from app.keys import resolve_ingestion_key

app = Flask(__name__)

hostname = socket.gethostname()

mongo = None


def get_mongo():
    global mongo

    if mongo is None:

        mongo = HerringboneMongoDatabase(
            user=os.environ.get("MONGO_USER", "admin"),
            password=os.environ.get("MONGO_PASS", "secret"),
            database=os.environ.get("DB_NAME", "herringbone"),
            host=os.environ.get("MONGO_HOST", "localhost"),
            port=int(os.environ.get("MONGO_PORT", 27017)),
            replica_set=os.environ.get("MONGO_REPLICA_SET", None),
        )

        print("[✓] Mongo client initialized")

    return mongo


@app.route("/logingestion/remote", methods=["POST"])
def receiver_v2():

    try:
        mongo = get_mongo()
    except Exception as e:
        print(f"[✗] Mongo init failed: {e}")
        return ("Database initialization failed", 500)

    context_id = resolve_ingestion_key(request, mongo)

    if context_id is None:
        print("[✗] Invalid ingestion key")
        return ("Invalid ingestion key", 403)

    payload = request.get_json(silent=True)

    if not payload:
        return ("No data received", 400)

    remote = payload.get("remote_from")

    if (
        not isinstance(remote, dict)
        or "source_addr" not in remote
        or not remote["source_addr"]
    ):
        return ('Missing "remote_from.source_addr"', 400)

    addr = remote["source_addr"]

    data = payload.get("data")

    if data is None:
        return ('Missing "data"', 400)

    try:

        event_id = mongo.insert_event({
            "raw": data,
            "source": {
                "address": addr,
                "kind": "remote",
            },
            "event_time": datetime.now(UTC),
            "ingested_at": datetime.now(UTC),
            "receiver": {
                "hostname": hostname
            }
        }, context_id=context_id)

        mongo.upsert_event_state(event_id, {
            "parsed": False,
            "enriched": False,
            "detected": False,
            "severity": None,
        }, context_id=context_id)

        return ("Data received", 200)

    except Exception as e:
        print(f"[✗] Mongo insert failed: {e}")
        return ("Insert failed", 500)


def start_remote_receiver():

    print("Receiver type set to REMOTE")
    print("Listening on container port 7004")

    app.run(
        host="0.0.0.0",
        port=7004,
        threaded=True
    )