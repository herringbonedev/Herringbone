from flask import Flask, request
from datetime import datetime, UTC
import os

from modules.database.mongo_db import HerringboneMongoDatabase
from app.forwarder import forward_data

app = Flask(__name__)

forward_route = os.environ.get("FORWARD_ROUTE", None)


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET", None),
    )


def _client_ip():
    xff = request.headers.getlist("X-Forwarded-For")
    if xff:
        return xff[0].split(",")[0].strip()
    return request.remote_addr


@app.route("/logingestion/receiver", methods=["POST"])
def receiver():
    try:
        mongo = get_mongo()
    except Exception as e:
        return ("Database not initialized; check server logs for Mongo errors.", 500)

    data = request.get_json(silent=True) or None
    print(f"[*] Data received: {str(data)}")

    if not data:
        return ("No data received", 400)

    addr = _client_ip()
    print(f"[Source Address: {addr}] {data}")

    if forward_route is None:
        try:
            event_id = mongo.insert_event({
                "raw": data,
                "source": {
                    "address": addr,
                    "kind": "http",
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
    else:
        result = forward_data(forward_route, data, addr)
        if result:
            return ("Forward succeed", 200)
        else:
            return ("Forward failed", 500)


def start_http_receiver():
    print("Receiver type set to HTTP...")
    print("Started on container port 7004")
    app.run(host="0.0.0.0", port=7004, threaded=True)
