from flask import Flask, request, jsonify
import os
import socket

from modules.database.mongo_db import HerringboneMongoDatabase
from app.batcher import get_batch_writer
from app.keys import resolve_ingestion_key
from app.forwarder import forward_data, forward_many, get_forward_batcher

app = Flask(__name__)

forward_route = os.environ.get("FORWARD_ROUTE")
hostname = socket.gethostname()

mongo = None
batch_writer = None
HTTP_MAX_BATCH_SIZE = int(os.environ.get("HTTP_MAX_BATCH_SIZE", "5000"))


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
        print("[✓] MongoDB client initialized", flush=True)

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


def _require_context_from_key():
    context_id = resolve_ingestion_key(request, get_mongo())
    if context_id is None:
        print("[✗] Invalid ingestion key", flush=True)
        return None
    return context_id


def _normalize_http_events(payload):
    if isinstance(payload, list):
        return [event for event in payload[:HTTP_MAX_BATCH_SIZE] if isinstance(event, dict)]

    if not isinstance(payload, dict):
        return []

    events = payload.get("events")
    if isinstance(events, list):
        normalized = []
        for event in events[:HTTP_MAX_BATCH_SIZE]:
            if not isinstance(event, dict):
                continue
            normalized.append({
                "data": event.get("data", event.get("raw", event)),
                "source_addr": event.get("source_addr") or payload.get("source_addr") or _client_ip() or "http",
                "kind": event.get("kind") or "http",
            })
        return normalized

    return [{
        "data": payload,
        "source_addr": _client_ip() or "http",
        "kind": "http",
    }]


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
        stats = get_forward_batcher(forward_route).stats() if forward_route else get_writer().stats()
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
    context_id = _require_context_from_key()
    if context_id is None:
        return ("Invalid ingestion key", 403)

    payload = request.get_json(silent=True)
    if payload is None:
        return ("No data received", 400)

    events = _normalize_http_events(payload)
    if not events:
        return ('Missing data or non-empty "events" array', 400)

    if forward_route:
        accepted, dropped = forward_many(forward_route, events)
        if len(events) == 1 and dropped == 0:
            return ("Forward accepted", 202)
        return jsonify({"accepted": accepted, "dropped": dropped}), 202 if dropped == 0 else 207

    writer = get_writer()
    accepted = 0
    dropped = 0

    for event in events:
        data = event.get("data")
        if data is None:
            dropped += 1
            continue
        if writer.enqueue(data, event.get("source_addr") or _client_ip() or "http", event.get("kind") or "http", context_id):
            accepted += 1
        else:
            dropped += 1

    if len(events) == 1 and dropped == 0:
        return ("Data received", 200)

    return jsonify({"accepted": accepted, "dropped": dropped}), 200 if dropped == 0 else 207


@app.route("/logingestion/receiver/bulk", methods=["POST"])
@app.route("/logingestion/receiver/batch", methods=["POST"])
def receiver_bulk():
    return receiver()


def start_http_receiver():
    print("Receiver type set to HTTP", flush=True)
    print("Listening on container port 7004", flush=True)

    if forward_route:
        get_forward_batcher(forward_route)
    else:
        get_writer()

    app.run(host="0.0.0.0", port=7004, threaded=True)
