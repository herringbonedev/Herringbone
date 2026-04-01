import os
import requests
import socket
from datetime import datetime, UTC

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.audit import AuditLogger


INGESTION_KEY = os.environ.get("INGESTION_KEY", None)
FORWARD_TIMEOUT = int(os.environ.get("FORWARD_TIMEOUT", 5))


def get_audit_logger():
    mongo = HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET", None),
    )
    return AuditLogger(mongo)


def forward_data(route, data, source_addr):
    """
    Forwards log to remote receiver route.

    Supports authenticated ingestion using INGESTION_KEY.
    Includes security audit logging.
    """

    audit = None

    try:
        audit = get_audit_logger()
    except Exception:
        # audit logging should never break ingestion
        audit = None

    payload = {
        "remote_from": {
            "source_addr": source_addr
        },
        "data": data
    }

    headers = {
        "Content-Type": "application/json"
    }

    if INGESTION_KEY:
        headers["X-Herringbone-Key"] = INGESTION_KEY

    try:
        response = requests.post(
            route,
            json=payload,
            headers=headers,
            timeout=FORWARD_TIMEOUT
        )

        if 200 <= response.status_code < 300:
            print(f"[✓] Forwarded log to {route}")
            return True

        print(
            f"[✗] Forward rejected by {route} "
            f"status={response.status_code} "
            f"body={response.text}"
        )

        if audit:
            audit.log(
                event="log_forward_rejected",
                severity="warning",
                details={
                    "route": route,
                    "status": response.status_code,
                    "source_addr": source_addr,
                    "receiver_host": socket.gethostname(),
                    "time": datetime.now(UTC).isoformat(),
                }
            )

        return False

    except requests.exceptions.Timeout:

        print(f"[✗] Forward timeout to {route}")

        if audit:
            audit.log(
                event="log_forward_timeout",
                severity="warning",
                details={
                    "route": route,
                    "source_addr": source_addr,
                    "receiver_host": socket.gethostname(),
                    "time": datetime.now(UTC).isoformat(),
                }
            )

        return False

    except requests.exceptions.ConnectionError as e:

        print(f"[✗] Connection error forwarding to {route}: {e}")

        if audit:
            audit.log(
                event="log_forward_connection_error",
                severity="error",
                details={
                    "route": route,
                    "source_addr": source_addr,
                    "error": str(e),
                    "receiver_host": socket.gethostname(),
                    "time": datetime.now(UTC).isoformat(),
                }
            )

        return False

    except Exception as e:

        print(f"[✗] Unexpected forwarding error: {e}")

        if audit:
            audit.log(
                event="log_forward_exception",
                severity="error",
                details={
                    "route": route,
                    "source_addr": source_addr,
                    "error": str(e),
                    "receiver_host": socket.gethostname(),
                    "time": datetime.now(UTC).isoformat(),
                }
            )

        return False