from flask import Flask, request
from datetime import datetime
import os
from modules.database.mongo_db import HerringboneMongoDatabase

app = Flask(__name__)

def get_mongo():
    """
    Initialize a MongoDB handler from environment variables.
    Returns an instance or raises an Exception (caught at import time below).
    """
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        collection=os.environ.get("COLLECTION_NAME", "logs"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=(os.environ.get("MONGO_REPLICA_SET", None))
    )

# Create a single reusable instance for this process
try:
    print("Connecting to database...")
    mongo = get_mongo()
    print("[✓] Mongo handler initialized")
except Exception as e:
    print(f"[✗] Mongo connection init failed: {e}")
    mongo = None  # allow app to start; requests will error cleanly

@app.route("/logingestion/remote", methods=["POST"])
def receiver_v2():
    if mongo is None:
        return ("Database not initialized; check server logs for Mongo errors.", 500)

    payload = request.get_json(silent=True) or None
    print(f"[*] Payload received: {payload}")

    if not payload:
        return ("No data received", 400)

    remote = payload.get("remote_from")
    if (
        not isinstance(remote, dict)      # remote_from missing or wrong type
        or "source_addr" not in remote     # key missing
        or not remote["source_addr"]       # empty, null, or ""
    ):
        return ('Missing "remote_from.source_addr"', 400)

    addr = remote["source_addr"]
    data = payload.get("data")

    if data is None:
        return ('Missing "data"', 400)

    print(f"[Source Address: {addr}] {data}")

    try:
        mongo.insert_log(
            {
                "source_address": addr,
                "raw_log": data,
                "recon": False,
                "detected": False,
                "status": None,
                "last_update": datetime.utcnow(),
            },
            clean_codec=True,
        )
        return ("Data received", 200)

    except Exception as e:
        print(f"[✗] Mongo insert operation failed: {e}")
        return (f"Insert failed: {e}", 500)


def start_remote_receiver():
    print("Receiver type set to REMOTE...")
    print("Started on container port 7004")
    app.run(host="0.0.0.0", port=7004, threaded=True)