from flask import Flask, request
from datetime import datetime, UTC
import os
import socket

from modules.database.mongo_db import HerringboneMongoDatabase
from app.keys import resolve_ingestion_key
from app.forwarder import forward_data


app = Flask(__name__)

forward_route = os.environ.get("FORWARD_ROUTE")
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

        print("[✓] MongoDB client initialized")

    return mongo


def _client_ip():
    xff = request.headers.get("X-Forwarded-For")

    if xff:
        return xff.split(",")[0].strip()

    return request.remote_addr


@app.route("/logingestion/receiver", methods=["POST"])
def receiver():

    mongo = get_mongo()

    context_id = resolve_ingestion_key(request, mongo)

    if context_id is None:
        print("[✗] Invalid ingestion key")
        return ("Invalid ingestion key", 403)

    data = request.get_json(silent=True)

    if not data:
        return ("No data received", 400)

    addr = _client_ip()

    # Forwarding mode (edge receiver)
    if forward_route:

        result = forward_data(forward_route, data, addr)

        if result:
            return ("Forward succeed", 200)

        print("[✗] Forwarding failed")

        return ("Forward failed", 500)

    # Local ingestion mode
    try:

        event_id = mongo.insert_event({
            "raw": data,
            "source": {
                "address": addr,
                "kind": "http",
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


def start_http_receiver():

    print("Receiver type set to HTTP")
    print("Listening on container port 7004")

    app.run(
        host="0.0.0.0",
        port=7004,
        threaded=True
    )