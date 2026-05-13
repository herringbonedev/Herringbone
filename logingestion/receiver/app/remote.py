from flask import Flask, request, jsonify
import os
import socket

from modules.database.mongo_db import HerringboneMongoDatabase
from logingestion.receiver.app.batcher import get_batch_writer
from logingestion.receiver.app.keys import resolve_ingestion_key

app = Flask(__name__)

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

        print("[✓] Mongo client initialized")

    return mongo


def get_writer():
    global batch_writer

    if batch_writer is None:
        batch_writer = get_batch_writer(get_mongo())

    return batch_writer


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "herringbone-receiver",
        "receiver_type": "REMOTE",
        "status": "ok",
        "hostname": hostname,
    }), 200


@app.route("/ready", methods=["GET"])
def ready():
    try:
        get_mongo()
        return jsonify({
            "service": "herringbone-receiver",
            "receiver_type": "REMOTE",
            "status": "ready",
            "stats": get_writer().stats(),
        }), 200
    except Exception as exc:
        return jsonify({
            "service": "herringbone-receiver",
            "receiver_type": "REMOTE",
            "status": "not_ready",
            "error": str(exc),
        }), 503


@app.route("/logingestion/remote", methods=["POST"])
def receiver_v2():
    mongo = get_mongo()
    context_id = resolve_ingestion_key(request, mongo)

    if context_id is None:
        print("[✗] Invalid ingestion key")
        return ("Invalid ingestion key", 403)

    payload = request.get_json(silent=True)

    if not payload:
        return ("No data received", 400)

    remote = payload.get("remote_from")

    if not isinstance(remote, dict) or "source_addr" not in remote or not remote["source_addr"]:
        return ('Missing "remote_from.source_addr"', 400)

    data = payload.get("data")

    if data is None:
        return ('Missing "data"', 400)

    if not get_writer().enqueue(data, remote["source_addr"], "remote", context_id):
        return ("Receiver queue full", 503)

    return ("Data received", 200)


@app.route("/logingestion/remote/bulk", methods=["POST"])
def receiver_bulk():
    mongo = get_mongo()
    context_id = resolve_ingestion_key(request, mongo)

    if context_id is None:
        print("[✗] Invalid ingestion key")
        return ("Invalid ingestion key", 403)

    payload = request.get_json(silent=True)

    if not payload:
        return ("No data received", 400)

    events = payload.get("events")

    if not isinstance(events, list) or not events:
        return ('Missing non-empty "events" array', 400)

    writer = get_writer()
    accepted = 0
    dropped = 0

    for event in events:
        if not isinstance(event, dict):
            dropped += 1
            continue

        data = event.get("data")
        source_addr = event.get("source_addr") or payload.get("source_addr") or "remote"

        if data is None:
            dropped += 1
            continue

        if writer.enqueue(data, source_addr, "remote", context_id):
            accepted += 1
        else:
            dropped += 1

    status = 200 if dropped == 0 else 207

    return jsonify({
        "accepted": accepted,
        "dropped": dropped,
    }), status


def start_remote_receiver():
    print("Receiver type set to REMOTE")
    print("Listening on container port 7004")

    get_writer()

    app.run(
        host="0.0.0.0",
        port=7004,
        threaded=True
    )
