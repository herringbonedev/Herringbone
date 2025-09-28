from flask import Flask, request
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
        port=int(os.environ.get("MONGO_PORT", 27017))
    )

# Create a single reusable instance for this process
try:
    print("Connecting to database...")
    mongo = get_mongo()
    print("[✓] Mongo handler initialized")
except Exception as e:
    print(f"[✗] Mongo connection init failed: {e}")
    mongo = None  # allow app to start; requests will error cleanly

def _client_ip():
    """
    Best-effort client IP detection:
    - Prefer X-Forwarded-For (first hop) if present (behind proxy/ingress)
    - Fallback to Flask's request.remote_addr
    """
    xff = request.headers.getlist("X-Forwarded-For")
    if xff:
        return xff[0].split(",")[0].strip()
    return request.remote_addr

@app.route("/receiver", methods=["GET"])
def receiver():
    if mongo is None:
        return ("Database not initialized; check server logs for Mongo errors.", 500)

    data = request.args.get("data")
    if not data:
        return ("No data received", 400)

    addr = _client_ip()
    print(f"[Source Address: {addr}] {data}")

    try:
        mongo.insert_log(
            {"source_address": addr, "raw_log": data},
            clean_codec=True  # apply your legacy clean/escape behavior
        )
        return ("Data received", 200)
    except Exception as e:
        print(f"[✗] Mongo insert operation failed: {e}")
        return (f"Insert failed: {e}", 500)

def start_http_receiver():
    print("Receiver type set to HTTP...")
    print("Started on container port 7002")
    # Use threaded=True so multiple requests don't block each other
    app.run(host="0.0.0.0", port=7002, threaded=True)
