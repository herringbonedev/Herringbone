import os
import queue
import socket
import threading
import time
from datetime import datetime, UTC

import requests

try:
    from modules.database.mongo_db import HerringboneMongoDatabase
    from modules.audit import AuditLogger
except Exception:  # pragma: no cover - audit is best effort for receiver forwarding
    HerringboneMongoDatabase = None
    AuditLogger = None


INGESTION_KEY = os.environ.get("INGESTION_KEY", "")
FORWARD_TIMEOUT = float(os.environ.get("FORWARD_TIMEOUT", "5"))
FORWARD_QUEUE = int(os.environ.get("FORWARD_QUEUE", os.environ.get("RECEIVER_QUEUE", "250000")))
FORWARD_WORKERS = int(os.environ.get("FORWARD_WORKERS", os.environ.get("RECEIVER_WORKERS", "8")))
FORWARD_BATCH_SIZE = int(os.environ.get("FORWARD_BATCH_SIZE", os.environ.get("RECEIVER_BATCH_SIZE", "1000")))
FORWARD_BATCH_FLUSH_MS = int(os.environ.get("FORWARD_BATCH_FLUSH_MS", os.environ.get("RECEIVER_BATCH_FLUSH_MS", "100")))
FORWARD_HEARTBEAT_ENABLED = os.environ.get("FORWARD_HEARTBEAT_ENABLED", "true").lower() in ("1", "true", "yes")
FORWARD_HEARTBEAT_INTERVAL = float(os.environ.get("FORWARD_HEARTBEAT_INTERVAL", "5.0"))
FORWARD_DROP_LOG_INTERVAL = float(os.environ.get("FORWARD_DROP_LOG_INTERVAL", "5.0"))
FORWARD_FALLBACK_SINGLE = os.environ.get("FORWARD_FALLBACK_SINGLE", "true").lower() in ("1", "true", "yes")

_forwarders = {}
_forwarders_lock = threading.Lock()
_audit_logger = None
_audit_lock = threading.Lock()


def _bulk_route(route: str) -> str:
    override = os.environ.get("FORWARD_BULK_ROUTE", "").strip()
    if override:
        return override

    route = (route or "").strip()
    if route.endswith("/bulk") or route.endswith("/batch"):
        return route
    if route.endswith("/logingestion/remote"):
        return f"{route}/bulk"
    if route.endswith("/logingestion/receiver"):
        return f"{route}/bulk"
    return f"{route.rstrip('/')}/bulk"


def _single_payload(data, source_addr):
    return {
        "remote_from": {
            "source_addr": source_addr,
        },
        "data": data,
    }


def _batch_payload(batch):
    return {
        "events": [
            {
                "data": item["data"],
                "source_addr": item.get("source_addr") or "forwarded",
                "kind": item.get("kind") or "forwarded",
            }
            for item in batch
        ]
    }


def _headers():
    headers = {"Content-Type": "application/json"}
    if INGESTION_KEY:
        headers["X-Herringbone-Key"] = INGESTION_KEY
    return headers


def get_audit_logger():
    global _audit_logger

    if HerringboneMongoDatabase is None or AuditLogger is None:
        return None

    with _audit_lock:
        if _audit_logger is not None:
            return _audit_logger

        try:
            mongo = HerringboneMongoDatabase(
                user=os.environ.get("MONGO_USER", "admin"),
                password=os.environ.get("MONGO_PASS", "secret"),
                database=os.environ.get("DB_NAME", "herringbone"),
                host=os.environ.get("MONGO_HOST", "localhost"),
                port=int(os.environ.get("MONGO_PORT", 27017)),
                auth_source=os.environ.get("AUTH_DB", "admin"),
                replica_set=os.environ.get("MONGO_REPLICA_SET", None),
            )
            _audit_logger = AuditLogger(mongo)
        except Exception:
            _audit_logger = None

        return _audit_logger


def _audit_failure(event, severity, details):
    try:
        audit = get_audit_logger()
        if audit:
            audit.log(event=event, severity=severity, details=details)
    except Exception:
        pass


class ForwardBatcher:
    def __init__(self, route: str):
        self.route = route
        self.bulk_route = _bulk_route(route)
        self.queue = queue.Queue(maxsize=FORWARD_QUEUE)
        self.started = False
        self.lock = threading.Lock()
        self.drop_lock = threading.Lock()

        self.queued_total = 0
        self.forwarded_total = 0
        self.dropped_total = 0
        self.failed_total = 0
        self.flush_total = 0

        self.last_queued_total = 0
        self.last_forwarded_total = 0
        self.last_dropped_total = 0
        self.last_failed_total = 0
        self.last_flush_total = 0
        self.last_heartbeat = time.monotonic()

        self.last_drop_log = 0.0
        self.drops_since_log = 0

    def start(self):
        if self.started:
            return

        self.started = True

        for index in range(FORWARD_WORKERS):
            thread = threading.Thread(target=self._worker, name=f"forward-batcher-{index}", daemon=True)
            thread.start()

        if FORWARD_HEARTBEAT_ENABLED:
            thread = threading.Thread(target=self._heartbeat_worker, name="forward-batcher-heartbeat", daemon=True)
            thread.start()

        print(
            f"[✓] Forward batcher started workers={FORWARD_WORKERS} "
            f"batch_size={FORWARD_BATCH_SIZE} flush_ms={FORWARD_BATCH_FLUSH_MS} "
            f"queue={FORWARD_QUEUE} route={self.bulk_route}",
            flush=True,
        )

    def enqueue(self, data, source_addr, kind="forwarded") -> bool:
        item = {
            "data": data,
            "source_addr": source_addr,
            "kind": kind,
        }

        try:
            self.queue.put_nowait(item)
        except queue.Full:
            with self.lock:
                self.dropped_total += 1
            self._log_drop()
            return False

        with self.lock:
            self.queued_total += 1

        return True

    def enqueue_many(self, events) -> tuple[int, int]:
        accepted = 0
        dropped = 0
        for event in events:
            if not isinstance(event, dict):
                dropped += 1
                continue
            data = event.get("data")
            if data is None:
                dropped += 1
                continue
            if self.enqueue(data, event.get("source_addr") or "forwarded", event.get("kind") or "forwarded"):
                accepted += 1
            else:
                dropped += 1
        return accepted, dropped

    def stats(self):
        with self.lock:
            return {
                "route": self.route,
                "bulk_route": self.bulk_route,
                "queued_total": self.queued_total,
                "forwarded_total": self.forwarded_total,
                "dropped_total": self.dropped_total,
                "failed_total": self.failed_total,
                "flush_total": self.flush_total,
                "queue_depth": self.queue.qsize(),
                "workers": FORWARD_WORKERS,
                "batch_size": FORWARD_BATCH_SIZE,
                "batch_flush_ms": FORWARD_BATCH_FLUSH_MS,
            }

    def _log_drop(self):
        now = time.monotonic()
        with self.drop_lock:
            self.drops_since_log += 1
            if now - self.last_drop_log < FORWARD_DROP_LOG_INTERVAL:
                return
            dropped = self.drops_since_log
            self.drops_since_log = 0
            self.last_drop_log = now

        print(
            f"[✗] Forward queue full — dropped {dropped} messages in last {FORWARD_DROP_LOG_INTERVAL}s "
            f"queue_depth={self.queue.qsize()}",
            flush=True,
        )

    def _heartbeat_worker(self):
        while True:
            time.sleep(FORWARD_HEARTBEAT_INTERVAL)
            self._log_heartbeat()

    def _log_heartbeat(self):
        now = time.monotonic()
        with self.lock:
            elapsed = max(now - self.last_heartbeat, 0.001)
            queued_delta = self.queued_total - self.last_queued_total
            forwarded_delta = self.forwarded_total - self.last_forwarded_total
            dropped_delta = self.dropped_total - self.last_dropped_total
            failed_delta = self.failed_total - self.last_failed_total
            flush_delta = self.flush_total - self.last_flush_total

            self.last_queued_total = self.queued_total
            self.last_forwarded_total = self.forwarded_total
            self.last_dropped_total = self.dropped_total
            self.last_failed_total = self.failed_total
            self.last_flush_total = self.flush_total
            self.last_heartbeat = now

            queue_depth = self.queue.qsize()
            queued_total = self.queued_total
            forwarded_total = self.forwarded_total
            dropped_total = self.dropped_total
            failed_total = self.failed_total
            flush_total = self.flush_total

        avg_batch = round(forwarded_delta / flush_delta, 2) if flush_delta else 0
        print(
            "{"
            f"\"event\":\"forwarder_heartbeat\","
            f"\"interval_sec\":{round(elapsed, 3)},"
            f"\"queued_per_sec\":{round(queued_delta / elapsed, 2)},"
            f"\"forwarded_per_sec\":{round(forwarded_delta / elapsed, 2)},"
            f"\"dropped_per_sec\":{round(dropped_delta / elapsed, 2)},"
            f"\"failed_per_sec\":{round(failed_delta / elapsed, 2)},"
            f"\"queue_depth\":{queue_depth},"
            f"\"flushes\":{flush_delta},"
            f"\"avg_batch_size\":{avg_batch},"
            f"\"queued_total\":{queued_total},"
            f"\"forwarded_total\":{forwarded_total},"
            f"\"dropped_total\":{dropped_total},"
            f"\"failed_total\":{failed_total},"
            f"\"flush_total\":{flush_total},"
            f"\"workers\":{FORWARD_WORKERS},"
            f"\"batch_size\":{FORWARD_BATCH_SIZE}"
            "}",
            flush=True,
        )

    def _worker(self):
        session = requests.Session()
        while True:
            batch = []
            try:
                first = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            batch.append(first)
            deadline = time.monotonic() + (FORWARD_BATCH_FLUSH_MS / 1000.0)

            while len(batch) < FORWARD_BATCH_SIZE:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    batch.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break

            try:
                self._flush(session, batch)
                with self.lock:
                    self.forwarded_total += len(batch)
                    self.flush_total += 1
            except Exception as exc:
                with self.lock:
                    self.failed_total += len(batch)
                print(f"[✗] Forward batch failed size={len(batch)} route={self.bulk_route} error={exc}", flush=True)
                _audit_failure(
                    "log_forward_batch_failed",
                    "error",
                    {
                        "route": self.bulk_route,
                        "batch_size": len(batch),
                        "error": str(exc),
                        "receiver_host": socket.gethostname(),
                        "time": datetime.now(UTC).isoformat(),
                    },
                )
            finally:
                for _ in batch:
                    self.queue.task_done()

    def _flush(self, session: requests.Session, batch):
        if not batch:
            return

        response = session.post(
            self.bulk_route,
            json=_batch_payload(batch),
            headers=_headers(),
            timeout=FORWARD_TIMEOUT,
        )

        if 200 <= response.status_code < 300:
            return

        if response.status_code in (404, 405) and FORWARD_FALLBACK_SINGLE:
            self._flush_single_fallback(session, batch)
            return

        raise RuntimeError(f"remote rejected status={response.status_code} body={response.text[:500]}")

    def _flush_single_fallback(self, session: requests.Session, batch):
        for item in batch:
            response = session.post(
                self.route,
                json=_single_payload(item["data"], item.get("source_addr") or "forwarded"),
                headers=_headers(),
                timeout=FORWARD_TIMEOUT,
            )
            if not (200 <= response.status_code < 300):
                raise RuntimeError(f"remote rejected single status={response.status_code} body={response.text[:500]}")


def get_forward_batcher(route: str) -> ForwardBatcher:
    if not route:
        raise RuntimeError("forward route is required")

    with _forwarders_lock:
        batcher = _forwarders.get(route)
        if batcher is None:
            batcher = ForwardBatcher(route)
            _forwarders[route] = batcher
            batcher.start()
        return batcher


def forward_data(route, data, source_addr, kind="forwarded"):
    """Queue one log for batched forwarding. Returns False only if local forward queue is full."""
    return get_forward_batcher(route).enqueue(data, source_addr, kind)


def forward_many(route, events):
    """Queue many logs for batched forwarding. Returns (accepted, dropped)."""
    return get_forward_batcher(route).enqueue_many(events)
