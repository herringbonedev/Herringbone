import logging
import json
import os
import socket
import uuid
from datetime import datetime, UTC
from typing import Optional, Dict, Any

from fastapi import Request

audit_logger = logging.getLogger("herringbone.audit")

if not audit_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False


class AuditLogger:

    def __init__(self, mongo=None):

        self.mongo = mongo

        self.service = os.environ.get("HERRINGBONE_SERVICE")
        self.unit = os.environ.get("HERRINGBONE_UNIT")
        self.element = os.environ.get("HERRINGBONE_ELEMENT")

        self.instance = socket.gethostname()
        self.node = os.environ.get("NODE_NAME")

    def _emit(self, severity: str, record: Dict[str, Any]):

        msg = json.dumps(record, default=str)

        if severity == "INFO":
            audit_logger.info(msg)

        elif severity == "WARNING":
            audit_logger.warning(msg)

        elif severity == "ERROR":
            audit_logger.error(msg)

        elif severity == "CRITICAL":
            audit_logger.critical(msg)

        else:
            audit_logger.info(msg)

    def log(
        self,
        event: str,
        *,
        identity: Optional[dict] = None,
        request: Optional[Request] = None,
        target: Optional[str] = None,
        result: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):

        if not severity:
            severity = "INFO" if result == "success" else "WARNING"

        if not trace_id:
            trace_id = str(uuid.uuid4())

        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        meta = metadata or {}
        meta_json = json.dumps(meta)
        if len(meta_json) > 2048:
            meta = {"truncated": True}

        record = {
            "timestamp": timestamp,
            "event": event,
            "severity": severity,
            "result": result,
            "trace_id": trace_id,
            "service": self.service,
            "unit": self.unit,
            "element": self.element,
            "instance": self.instance,
            "node": self.node,
            "target": target,
            "context_id": "default",
            "user_id": None,
            "email": None,
            "service_id": None,
            "service_name": None,
            "source_ip": None,
            "path": None,
            "method": None,
            "metadata": meta,
        }

        if identity:

            record["context_id"] = identity.get("context_id", "default")

            record["user_id"] = identity.get("id") or identity.get("sub")
            record["email"] = identity.get("email")

            if identity.get("type") == "service":
                record["service_name"] = identity.get("service")
                record["service_id"] = identity.get("service_id")

            record["scopes"] = identity.get("scopes")

        if request:

            if request.client:
                record["source_ip"] = request.client.host

            record["path"] = request.url.path
            record["method"] = request.method

        self._emit(severity, record)

        if self.mongo:
            try:
                self.mongo.insert_one("audit_log", record)
            except Exception as e:
                audit_logger.error(
                    json.dumps({
                        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "severity": "ERROR",
                        "event": "audit_mongo_write_failed",
                        "error": str(e),
                        "service": self.service,
                        "instance": self.instance,
                    })
                )