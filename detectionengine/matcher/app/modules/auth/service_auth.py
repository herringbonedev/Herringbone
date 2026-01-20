import os
import requests
import socket
import uuid

AUTH_URL = os.environ.get("AUTH_URL", "http://herringbone-auth:7001")
SERVICE_NAME = os.environ.get("SERVICE_NAME") or socket.gethostname()
SERVICE_SECRET = os.environ.get("SERVICE_SECRET")

_cached_token = None


def get_service_token() -> str:
    global _cached_token

    if _cached_token:
        return _cached_token

    if not SERVICE_SECRET:
        raise RuntimeError("SERVICE_SECRET not set")

    payload = {
        "service": SERVICE_NAME,
        "secret": SERVICE_SECRET,
        "instance_id": f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}",
        "version": os.environ.get("SERVICE_VERSION", "dev"),
    }

    print("[*] service auth: requesting token")

    res = requests.post(f"{AUTH_URL}/herringbone/auth/service/login", json=payload, timeout=5)

    if not res.ok:
        raise RuntimeError(f"service auth failed: {res.text}")

    token = res.json()["access_token"]
    _cached_token = token

    print("[✓] service auth token acquired")

    return token
