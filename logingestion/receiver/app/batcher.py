from datetime import datetime, UTC
from pymongo import UpdateOne
from bson import ObjectId
import os
import queue
import socket
import threading
import time

hostname = socket.gethostname()

BATCH_SIZE = int(os.environ.get("RECEIVER_BATCH_SIZE", 500))
BATCH_FLUSH_MS = int(os.environ.get("RECEIVER_BATCH_FLUSH_MS", 250))
QUEUE_SIZE = int(os.environ.get("RECEIVER_QUEUE", 20000))
WORKER_THREADS = int(os.environ.get("RECEIVER_WORKERS", 4))
EVENTS_COLLECTION = os.environ.get("EVENTS_COLLECTION", "events")
EVENT_STATE_COLLECTION = os.environ.get("EVENT_STATE_COLLECTION", "event_state")
BATCH_DIRECT_MONGO = os.environ.get("BATCH_DIRECT_MONGO", "true").lower() in ("1", "true", "yes")

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
        self.lock = threading.Lock()

    def start(self):
        if self.started:
            return

        self.started = True

        for index in range(WORKER_THREADS):
            thread = threading.Thread(target=self._worker, name=f"mongo-batch-writer-{index}", daemon=True)
            thread.start()

        print(
            f"[✓] Mongo batch writer started workers={WORKER_THREADS} "
            f"batch_size={BATCH_SIZE} flush_ms={BATCH_FLUSH_MS} queue={QUEUE_SIZE}"
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
                "queue_depth": self.queue.qsize(),
                "workers": WORKER_THREADS,
                "batch_size": BATCH_SIZE,
                "batch_flush_ms": BATCH_FLUSH_MS,
            }

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
            except Exception as exc:
                with self.lock:
                    self.failed_total += len(batch)
                print(f"[✗] Mongo batch insert failed size={len(batch)} error={exc}")
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
        events = self._collection(EVENTS_COLLECTION)
        event_state = self._collection(EVENT_STATE_COLLECTION)

        event_docs = []
        state_ops = []
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
                "receiver": {
                    "hostname": hostname,
                    "batch": True,
                },
            })

            state_ops.append(UpdateOne(
                {
                    "event_id": event_id,
                    "context_id": context_id,
                },
                {
                    "$setOnInsert": {
                        "event_id": event_id,
                        "context_id": context_id,
                        "parsed": False,
                        "enriched": False,
                        "detected": False,
                        "severity": None,
                        "created_at": now,
                    },
                    "$set": {
                        "updated_at": now,
                    },
                },
                upsert=True,
            ))

        events.insert_many(event_docs, ordered=False)

        if state_ops:
            event_state.bulk_write(state_ops, ordered=False)

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
                "receiver": {
                    "hostname": hostname,
                    "batch": False,
                },
            }, context_id=context_id)

            self.mongo.upsert_event_state(event_id, {
                "parsed": False,
                "claimed": False,
                "claimed_by": "",
                "detected": False,
                "severity": None,
            }, context_id=context_id)

    def _collection(self, name):
        candidates = (
            "db",
            "database",
            "_db",
            "mongo_db",
        )

        for attr in candidates:
            value = getattr(self.mongo, attr, None)

            if value is None or isinstance(value, str):
                continue

            try:
                return value[name]
            except Exception:
                pass

        client = getattr(self.mongo, "client", None) or getattr(self.mongo, "_client", None)

        if client is not None:
            return client[os.environ.get("DB_NAME", "herringbone")][name]

        getter = getattr(self.mongo, "get_collection", None)

        if callable(getter):
            return getter(name)

        raise RuntimeError(
            "Unable to locate a pymongo database/client on HerringboneMongoDatabase. "
            "Set BATCH_DIRECT_MONGO=false to use wrapper mode, or expose .db/.client on the database wrapper."
        )
