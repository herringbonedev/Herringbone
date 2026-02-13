from flask import Flask, request
from datetime import datetime, UTC
import os
from modules.database.mongo_db import HerringboneMongoDatabase

app = Flask(__name__)

def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET", None),
    )

@app.route("/logingestion/remote", methods=["POST"])
def receiver_v2():
    try:
        mongo = get_mongo()
    except Exception as e:
        print(f"[✗] Mongo connection init failed: {e}")
        return ("Database not initialized; check server logs for Mongo errors.", 500)

    payload = request.get_json(silent=True) or None
    print(f"[*] Payload received: {payload}")

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

    print(f"[Source Address: {addr}] {data}")

    try:
        event_id = mongo.insert_event({
            "raw": data,
            "source": {
                "address": addr,
                "kind": "remote",
            },
            "event_time": datetime.now(UTC),
            "ingested_at": datetime.now(UTC),
        })

        mongo.upsert_event_state(event_id, {
            "parsed": False,
            "enriched": False,
            "detected": False,
            "severity": None,
        })

        return ("Data received", 200)

    except Exception as e:
        print(f"[✗] Mongo insert operation failed: {e}")
        return ("Insert failed; check server logs for details.", 500)


def start_remote_receiver():
    print("Receiver type set to REMOTE...")
    print("Started on container port 7004")
    app.run(host="0.0.0.0", port=7004, threaded=True)
