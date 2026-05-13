from flask import Flask, request, jsonify
import os
import socket

from modules.database.mongo_db import HerringboneMongoDatabase
from app.batcher import get_batch_writer
from app.keys import resolve_ingestion_key
from app.forwarder import forward_data

app = Flask(__name__)

forward_route = os.environ.get("FORWARD_ROUTE")
hostname = socket.gethostname()

mongo = None
batch_writer = None


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


def get_writer():
    global batch_writer

    if batch_writer is None:
        batch_writer = get_batch_writer(get_mongo())

    return batch_writer


def _client_ip():
    xff = request.headers.get("X-Forwarded-For")

    if xff:
        return xff.split(",")[0].strip()

    return request.remote_addr


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "herringbone-receiver",
        "receiver_type": "HTTP",
        "status": "ok",
        "hostname": hostname,
    }), 200


@app.route("/ready", methods=["GET"])
def ready():
    try:
        get_mongo()
        stats = get_writer().stats() if not forward_route else {}
        return jsonify({
            "service": "herringbone-receiver",
            "receiver_type": "HTTP",
            "status": "ready",
            "forwarding": bool(forward_route),
            "stats": stats,
        }), 200
    except Exception as exc:
        return jsonify({
            "service": "herringbone-receiver",
            "receiver_type": "HTTP",
            "status": "not_ready",
            "error": str(exc),
        }), 503


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

    if forward_route:
        result = forward_data(forward_route, data, addr)

        if result:
            return ("Forward succeed", 200)

        print("[✗] Forwarding failed")
        return ("Forward failed", 500)

    if not get_writer().enqueue(data, addr, "http", context_id):
        return ("Receiver queue full", 503)

    return ("Data received", 200)


def start_http_receiver():
    print("Receiver type set to HTTP")
    print("Listening on container port 7004")

    if not forward_route:
        get_writer()

    app.run(
        host="0.0.0.0",
        port=7004,
        threaded=True
    )
