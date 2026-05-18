from datetime import datetime, UTC
from pymongo import MongoClient, errors
from bson import ObjectId
import os
import queue
import socket
import threading
import time

hostname = socket.gethostname()

BATCH_SIZE = int(os.environ.get("RECEIVER_BATCH_SIZE", 1000))
BATCH_FLUSH_MS = int(os.environ.get("RECEIVER_BATCH_FLUSH_MS", 100))
QUEUE_SIZE = int(os.environ.get("RECEIVER_QUEUE", 250000))
WORKER_THREADS = int(os.environ.get("RECEIVER_WORKERS", 8))
EVENTS_COLLECTION = os.environ.get("EVENTS_COLLECTION", "events")
EVENT_STATE_COLLECTION = os.environ.get("EVENT_STATE_COLLECTION", "event_state")
BATCH_DIRECT_MONGO = os.environ.get("BATCH_DIRECT_MONGO", "true").lower() in ("1", "true", "yes")

RECEIVER_HEARTBEAT_ENABLED = os.environ.get("RECEIVER_HEARTBEAT_ENABLED", "true").lower() in ("1", "true", "yes")
RECEIVER_HEARTBEAT_INTERVAL = float(os.environ.get("RECEIVER_HEARTBEAT_INTERVAL", "5.0"))

MONGO_MAX_POOL_SIZE = int(os.environ.get("MONGO_MAX_POOL_SIZE", max(100, WORKER_THREADS * 20)))
MONGO_SERVER_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", 5000))
MONGO_RETRY_WRITES = os.environ.get("MONGO_RETRY_WRITES", "true").lower() in ("1", "true", "yes")

_writer = None
_writer_lock = threading.Lock()


def get_batch_writer(mongo):
    global _writer

    with _writer_lock:
        if _writer is None:
            _writer = MongoBatchWriter(mongo)
            _writer.start()

    return _writer


class MongoBatchWriter:
    def __init__(self, mongo):
        self.mongo = mongo
        self.queue = queue.Queue(maxsize=QUEUE_SIZE)
        self.started = False

        self.received_total = 0
        self.queued_total = 0
        self.dropped_total = 0
        self.inserted_total = 0
        self.failed_total = 0
        self.forwarded_total = 0
        self.flush_total = 0

        self.last_received_total = 0
        self.last_queued_total = 0
        self.last_dropped_total = 0
        self.last_inserted_total = 0
        self.last_failed_total = 0
        self.last_flush_total = 0
        self.last_heartbeat = time.monotonic()

        self.lock = threading.Lock()

        self._direct_client = None
        self._direct_db = None
        self._direct_lock = threading.Lock()

    def start(self):
        if self.started:
            return

        self.started = True

        for index in range(WORKER_THREADS):
            thread = threading.Thread(target=self._worker, name=f"mongo-batch-writer-{index}", daemon=True)
            thread.start()

        if RECEIVER_HEARTBEAT_ENABLED:
            heartbeat_thread = threading.Thread(target=self._heartbeat_worker, name="mongo-batch-writer-heartbeat", daemon=True)
            heartbeat_thread.start()

        print(
            f"[✓] Mongo batch writer started workers={WORKER_THREADS} "
            f"batch_size={BATCH_SIZE} flush_ms={BATCH_FLUSH_MS} queue={QUEUE_SIZE} "
            f"direct_mongo={BATCH_DIRECT_MONGO}"
        )

    def enqueue(self, data, source_addr, kind, context_id):
        item = {
            "data": data,
            "source_addr": source_addr,
            "kind": kind,
            "context_id": context_id,
        }

        with self.lock:
            self.received_total += 1

        try:
            self.queue.put_nowait(item)
        except queue.Full:
            with self.lock:
                self.dropped_total += 1
            return False

        with self.lock:
            self.queued_total += 1

        return True

    def stats(self):
        with self.lock:
            return {
                "received_total": self.received_total,
                "queued_total": self.queued_total,
                "dropped_total": self.dropped_total,
                "inserted_total": self.inserted_total,
                "failed_total": self.failed_total,
                "flush_total": self.flush_total,
                "queue_depth": self.queue.qsize(),
                "workers": WORKER_THREADS,
                "batch_size": BATCH_SIZE,
                "batch_flush_ms": BATCH_FLUSH_MS,
                "direct_mongo": BATCH_DIRECT_MONGO,
            }

    def _heartbeat_worker(self):
        while True:
            time.sleep(RECEIVER_HEARTBEAT_INTERVAL)
            self._log_heartbeat()

    def _log_heartbeat(self):
        now = time.monotonic()

        with self.lock:
            elapsed = max(now - self.last_heartbeat, 0.001)

            received_delta = self.received_total - self.last_received_total
            queued_delta = self.queued_total - self.last_queued_total
            dropped_delta = self.dropped_total - self.last_dropped_total
            inserted_delta = self.inserted_total - self.last_inserted_total
            failed_delta = self.failed_total - self.last_failed_total
            flush_delta = self.flush_total - self.last_flush_total

            self.last_received_total = self.received_total
            self.last_queued_total = self.queued_total
            self.last_dropped_total = self.dropped_total
            self.last_inserted_total = self.inserted_total
            self.last_failed_total = self.failed_total
            self.last_flush_total = self.flush_total
            self.last_heartbeat = now

            queue_depth = self.queue.qsize()
            received_total = self.received_total
            queued_total = self.queued_total
            dropped_total = self.dropped_total
            inserted_total = self.inserted_total
            failed_total = self.failed_total
            flush_total = self.flush_total

        avg_batch = round(inserted_delta / flush_delta, 2) if flush_delta else 0

        print(
            "{"
            f"\"event\":\"receiver_heartbeat\","
            f"\"interval_sec\":{round(elapsed, 3)},"
            f"\"received_per_sec\":{round(received_delta / elapsed, 2)},"
            f"\"queued_per_sec\":{round(queued_delta / elapsed, 2)},"
            f"\"inserted_per_sec\":{round(inserted_delta / elapsed, 2)},"
            f"\"dropped_per_sec\":{round(dropped_delta / elapsed, 2)},"
            f"\"failed_per_sec\":{round(failed_delta / elapsed, 2)},"
            f"\"queue_depth\":{queue_depth},"
            f"\"flushes\":{flush_delta},"
            f"\"avg_batch_size\":{avg_batch},"
            f"\"received_total\":{received_total},"
            f"\"queued_total\":{queued_total},"
            f"\"inserted_total\":{inserted_total},"
            f"\"dropped_total\":{dropped_total},"
            f"\"failed_total\":{failed_total},"
            f"\"flush_total\":{flush_total},"
            f"\"workers\":{WORKER_THREADS},"
            f"\"batch_size\":{BATCH_SIZE}"
            "}",
            flush=True,
        )

    def _worker(self):
        while True:
            batch = []

            try:
                first = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            batch.append(first)
            deadline = time.monotonic() + (BATCH_FLUSH_MS / 1000.0)

            while len(batch) < BATCH_SIZE:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    break

                try:
                    batch.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break

            try:
                self._flush(batch)
                with self.lock:
                    self.inserted_total += len(batch)
                    self.flush_total += 1
            except Exception as exc:
                with self.lock:
                    self.failed_total += len(batch)
                print(f"[✗] Mongo batch insert failed size={len(batch)} error={exc}", flush=True)
            finally:
                for _ in batch:
                    self.queue.task_done()

    def _flush(self, batch):
        if not batch:
            return

        if BATCH_DIRECT_MONGO:
            self._flush_direct(batch)
            return

        self._flush_wrapper(batch)

    def _flush_direct(self, batch):
        db = self._direct_database()
        events = db[EVENTS_COLLECTION]
        event_state = db[EVENT_STATE_COLLECTION]

        event_docs = []
        state_docs = []
        now = datetime.now(UTC)

        for item in batch:
            event_object_id = ObjectId()
            event_id = str(event_object_id)
            context_id = item["context_id"]

            event_docs.append({
                "_id": event_object_id,
                "event_id": event_id,
                "context_id": context_id,
                "raw": item["data"],
                "source": {
                    "address": item["source_addr"],
                    "kind": item["kind"],
                },
                "event_time": now,
                "ingested_at": now,
                "created_at": now,
                "receiver": {
                    "hostname": hostname,
                    "batch": True,
                },
            })

            # These are brand new generated event IDs, so insert_many is much
            # faster than bulk_write(UpdateOne(..., upsert=True)) and avoids a
            # second index lookup per event.
            state_docs.append({
                "event_id": event_id,
                "context_id": context_id,
                "parsed": False,
                "enriched": False,
                "detected": False,
                "claimed": False,
                "claimed_by": "",
                "lease_expires_at": None,
                "severity": None,
                "created_at": now,
                "updated_at": now,
                "last_stage": "receiver",
            })

        if event_docs:
            events.insert_many(event_docs, ordered=False)

        if state_docs:
            event_state.insert_many(state_docs, ordered=False)

    def _flush_wrapper(self, batch):
        for item in batch:
            now = datetime.now(UTC)
            context_id = item["context_id"]
            event_id = self.mongo.insert_event({
                "raw": item["data"],
                "source": {
                    "address": item["source_addr"],
                    "kind": item["kind"],
                },
                "event_time": now,
                "ingested_at": now,
                "created_at": now,
                "receiver": {
                    "hostname": hostname,
                    "batch": False,
                },
            }, context_id=context_id)

            self.mongo.upsert_event_state(event_id, {
                "parsed": False,
                "claimed": False,
                "claimed_by": "",
                "lease_expires_at": None,
                "detected": False,
                "severity": None,
                "last_stage": "receiver",
            }, context_id=context_id)

    def _direct_database(self):
        with self._direct_lock:
            if self._direct_db is not None:
                return self._direct_db

            uri = getattr(self.mongo, "uri", None)

            if uri:
                self._direct_client = MongoClient(
                    uri,
                    serverSelectionTimeoutMS=MONGO_SERVER_SELECTION_TIMEOUT_MS,
                    retryWrites=MONGO_RETRY_WRITES,
                    maxPoolSize=MONGO_MAX_POOL_SIZE,
                )
            else:
                user = os.environ.get("MONGO_USER", "")
                password = os.environ.get("MONGO_PASS", "")
                host = os.environ.get("MONGO_HOST", "mongodb")
                port = int(os.environ.get("MONGO_PORT", "27017"))
                database = os.environ.get("DB_NAME", "herringbone")
                auth_db = os.environ.get("AUTH_DB", "admin")

                if user and password:
                    mongo_uri = f"mongodb://{user}:{password}@{host}:{port}/{database}"
                else:
                    mongo_uri = f"mongodb://{host}:{port}/{database}"
                
                # authSource when it is explicitly provided through AUTH_DB.
                if auth_db:
                    sep = "&" if "?" in mongo_uri else "?"
                    mongo_uri = f"{mongo_uri}{sep}authSource={auth_db}"

                self._direct_client = MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=MONGO_SERVER_SELECTION_TIMEOUT_MS,
                    retryWrites=MONGO_RETRY_WRITES,
                    maxPoolSize=MONGO_MAX_POOL_SIZE,
                )

            self._direct_client.admin.command("ping")
            self._direct_db = self._direct_client[os.environ.get("DB_NAME", "herringbone")]
            return self._direct_db
