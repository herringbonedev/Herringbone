from flask import Flask, request, jsonify
import os
import socket

from modules.database.mongo_db import HerringboneMongoDatabase
from app.batcher import get_batch_writer
from app.keys import resolve_ingestion_key

app = Flask(__name__)

hostname = socket.gethostname()

mongo = None
batch_writer = None
REMOTE_MAX_BATCH_SIZE = int(os.environ.get("REMOTE_MAX_BATCH_SIZE", "5000"))


def get_mongo():
    global mongo

    if mongo is None:
        mongo = HerringboneMongoDatabase(
            user=os.environ.get("MONGO_USER", "admin"),
            password=os.environ.get("MONGO_PASS", "secret"),
            database=os.environ.get("DB_NAME", "herringbone"),
            host=os.environ.get("MONGO_HOST", "localhost"),
            port=int(os.environ.get("MONGO_PORT", 27017)),
            auth_source=os.environ.get("AUTH_DB", "admin"),
            replica_set=os.environ.get("MONGO_REPLICA_SET", None),
        )
        print("[✓] Mongo client initialized", flush=True)

    return mongo


def get_writer():
    global batch_writer

    if batch_writer is None:
        batch_writer = get_batch_writer(get_mongo())

    return batch_writer


def _require_context_from_key():
    context_id = resolve_ingestion_key(request, get_mongo())
    if context_id is None:
        print("[✗] Invalid ingestion key", flush=True)
        return None
    return context_id


def _normalize_events(payload):
    events = payload.get("events")
    if isinstance(events, list):
        return events[:REMOTE_MAX_BATCH_SIZE]

    data = payload.get("data")
    remote = payload.get("remote_from") or {}
    source_addr = remote.get("source_addr") or payload.get("source_addr") or request.remote_addr or "remote"
    if data is None:
        return []
    return [{"data": data, "source_addr": source_addr, "kind": "remote"}]


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
    context_id = _require_context_from_key()
    if context_id is None:
        return ("Invalid ingestion key", 403)

    payload = request.get_json(silent=True)
    if not payload:
        return ("No data received", 400)

    events = _normalize_events(payload)
    if not events:
        return ('Missing "data" or non-empty "events" array', 400)

    writer = get_writer()
    accepted = 0
    dropped = 0

    for event in events:
        if not isinstance(event, dict):
            dropped += 1
            continue
        data = event.get("data")
        source_addr = event.get("source_addr") or payload.get("source_addr") or request.remote_addr or "remote"
        kind = event.get("kind") or "remote"
        if data is None:
            dropped += 1
            continue
        if writer.enqueue(data, source_addr, kind, context_id):
            accepted += 1
        else:
            dropped += 1

    if len(events) == 1 and dropped == 0:
        return ("Data received", 200)

    return jsonify({"accepted": accepted, "dropped": dropped}), 200 if dropped == 0 else 207


@app.route("/logingestion/remote/bulk", methods=["POST"])
@app.route("/logingestion/remote/batch", methods=["POST"])
def receiver_bulk():
    return receiver_v2()


def start_remote_receiver():
    print("Receiver type set to REMOTE", flush=True)
    print("Listening on container port 7004", flush=True)
    get_writer()
    app.run(host="0.0.0.0", port=7004, threaded=True)
