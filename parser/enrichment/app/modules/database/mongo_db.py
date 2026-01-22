from __future__ import annotations

import inspect
import ipaddress
from urllib.parse import quote_plus
from functools import wraps
from typing import Any, Dict, Iterable
import codecs
from datetime import datetime

from pymongo import MongoClient, errors


# ===========================
# Connection Decorator
# ===========================

def with_connection(method):
    sig = inspect.signature(method)
    params = set(sig.parameters.keys())

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            client, db = self.open_mongo_connection()

            if "mongo_client" in params:
                kwargs["mongo_client"] = client
            if "mongo_db" in params:
                kwargs["mongo_db"] = db

            return method(self, *args, **kwargs)

        except errors.PyMongoError as e:
            raise RuntimeError(f"MongoDB operation failed: {e}") from e
        finally:
            self.close_mongo_connection()

    return wrapper


# ===========================
# URI Helpers
# ===========================

def _fmt_host(host: str) -> str:
    try:
        ip = ipaddress.ip_address(host)
        return f"[{host}]" if ip.version == 6 else host
    except ValueError:
        return host


def _split_host_port(host: str):
    if ":" in host and host.count(":") == 1:
        h, p = host.split(":")
        try:
            return h, int(p)
        except ValueError:
            pass
    return host, None


# ===========================
# Mongo Database Wrapper
# ===========================

class HerringboneMongoDatabase:
    """
    Abstract MongoDB access layer for Herringbone.

    Responsibilities:
    - Safe connection lifecycle
    - Canonical insert/update helpers
    - Schema boundary enforcement (by API shape)
    """

    def __init__(
        self,
        *,
        user: str,
        password: str,
        database: str,
        host: str,
        port: int = 27017,
        auth_source: str = "admin",
        replica_set: str | None = None,
    ):
        host_only, parsed_port = _split_host_port(host)
        port = parsed_port or port

        user_enc = quote_plus(user) if user else ""
        pass_enc = quote_plus(password) if password else ""
        auth = f"{user_enc}:{pass_enc}@" if user_enc or pass_enc else ""

        # qp = f"?authSource={quote_plus(auth_source)}"

        if replica_set:
            qp += f"&replicaSet={quote_plus(replica_set)}"

        self.uri = f"mongodb://{auth}{_fmt_host(host_only)}:{port}/{quote_plus(database)}{qp}"
        self.database = database

        self.client: MongoClient | None = None
        self.db = None

    # ===========================
    # Connection Management
    # ===========================

    def open_mongo_connection(self):
        self.client = MongoClient(
            self.uri,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
        )
        self.client.admin.command("ping")
        self.db = self.client[self.database]
        return self.client, self.db

    def close_mongo_connection(self):
        if self.client:
            self.client.close()
        self.client = None
        self.db = None

    # ===========================
    # Sanitization
    # ===========================

    @staticmethod
    def _clean_str(value: str) -> str:
        decoded = value.encode("utf-8").decode("unicode_escape")
        decoded = codecs.decode(decoded.encode("utf-8"), "unicode_escape")
        return decoded.strip()

    def sanitize(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self.sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.sanitize(v) for v in obj]
        if isinstance(obj, str):
            return self._clean_str(obj)
        return obj

    # ===========================
    # Core Operations
    # ===========================

    @with_connection
    def insert_one(self, collection: str, doc: dict, *, sanitize: bool = False, mongo_db):
        payload = self.sanitize(doc) if sanitize else dict(doc)
        return mongo_db[collection].insert_one(payload).inserted_id

    @with_connection
    def insert_many(self, collection: str, docs: Iterable[dict], *, sanitize: bool = False, mongo_db):
        payload = [self.sanitize(d) if sanitize else dict(d) for d in docs]
        return mongo_db[collection].insert_many(payload).inserted_ids

    @with_connection
    def upsert_one(
        self,
        collection: str,
        filter_query: dict,
        update_fields: dict,
        *,
        sanitize: bool = False,
        mongo_db
    ):
        fields = self.sanitize(update_fields) if sanitize else dict(update_fields)
        res = mongo_db[collection].update_one(
            filter_query,
            {"$set": fields},
            upsert=True,
        )
        return res.upserted_id

    @with_connection
    def find(
        self,
        collection: str,
        filter_query: dict,
        *,
        projection: dict | None = None,
        limit: int | None = None,
        mongo_db
    ):
        cur = mongo_db[collection].find(filter_query, projection)
        if limit:
            cur = cur.limit(limit)
        return list(cur)

    @with_connection
    def find_one(
        self,
        collection: str,
        filter_query: dict,
        *,
        projection: dict | None = None,
        mongo_db
    ):
        return mongo_db[collection].find_one(filter_query, projection)

    # ===========================
    # Canonical Herringbone APIs
    # ===========================

    # ---- Events (immutable) ----

    def insert_event(self, event: dict):
        """
        Insert a canonical immutable event.
        """
        return self.insert_one("events", event)

    # ---- Event State (mutable) ----

    def upsert_event_state(self, event_id, state: dict):
        """
        Create or update routing/UI state for an event.
        """
        state["last_updated"] = datetime.utcnow()
        return self.upsert_one(
            "event_state",
            {"event_id": event_id},
            state,
        )

    # ---- Results (append-only) ----

    def insert_parse_result(self, result: dict):
        return self.insert_one("parse_results", result)

    def insert_enrichment_result(self, result: dict):
        return self.insert_one("enrichment_results", result)

    def insert_detection(self, detection: dict):
        return self.insert_one("detections", detection)
