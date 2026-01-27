from __future__ import annotations

import inspect
import ipaddress
from urllib.parse import quote_plus
from functools import wraps
from typing import Any, Dict, Iterable, Tuple
from datetime import datetime
import codecs

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

            if "mongo_client" in params and "mongo_client" not in kwargs:
                kwargs["mongo_client"] = client
            if "mongo_db" in params and "mongo_db" not in kwargs:
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


def _split_host_port_if_present(host: str) -> Tuple[str, int | None]:
    h = host.strip()
    if not h:
        return h, None

    if h.startswith("["):
        rb = h.find("]")
        if rb != -1:
            inside = h[1:rb]
            after = h[rb + 1:]
            if after.startswith(":"):
                try:
                    return inside, int(after[1:])
                except ValueError:
                    return inside, None
            return inside, None

    if ":" in h and h.count(":") == 1:
        left, right = h.split(":", 1)
        try:
            return left, int(right)
        except ValueError:
            return h, None

    return h, None


# ===========================
# Main Class
# ===========================

class HerringboneMongoDatabase:
    """
    Unified MongoDB access layer for Herringbone (event-centric).

    Collections:
      - events (immutable)
      - event_state (mutable)
      - parse_results
      - enrichment_results
      - detections
    """

    def __init__(
        self,
        *,
        user: str = "",
        password: str = "",
        database: str,
        host: str = "localhost",
        port: int = 27017,
        auth_source: str = "admin",
        replica_set: str | None = None,
    ):
        host_only, parsed_port = _split_host_port_if_present(host)
        port_final = parsed_port if parsed_port is not None else port

        user_enc = quote_plus(user) if user else ""
        pass_enc = quote_plus(password) if password else ""
        auth_block = f"{user_enc}:{pass_enc}@" if (user_enc or pass_enc) else ""

        qp_parts = []

        # if auth_source:
        #     auth_source = auth_source.strip()
        #     if auth_source:
        #         qp_parts.append(f"authSource={quote_plus(auth_source)}")

        if replica_set:
            qp_parts.append(f"replicaSet={quote_plus(replica_set)}")
            qp_parts.append("readPreference=primary")
            qp_parts.append("directConnection=false")

        qp = ""
        if qp_parts:
            qp = "?" + "&".join(qp_parts)

        host_fmt = _fmt_host(host_only)
        self.uri = f"mongodb://{auth_block}{host_fmt}:{port_final}/{quote_plus(database)}{qp}"

        self.database = database

        self.client: MongoClient | None = None
        self.db = None

    # ===========================
    # Connection Management
    # ===========================

    def open_mongo_connection(self):
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                retryWrites=True,
            )
            self.client.admin.command("ping")
            self.db = self.client[self.database]
            return self.client, self.db

        except errors.ServerSelectionTimeoutError as e:
            raise RuntimeError(f"MongoDB server unreachable: {e}") from e
        except errors.OperationFailure as e:
            raise RuntimeError(f"MongoDB authentication failed: {e}") from e

    def close_mongo_connection(self):
        if self.client:
            try:
                self.client.close()
            finally:
                self.client = None
                self.db = None

    # ===========================
    # Sanitization
    # ===========================

    @staticmethod
    def _clean_codec_str(value: str) -> str:
        decoded = value.encode("utf-8").decode("unicode_escape")
        decoded = codecs.decode(decoded.encode("utf-8"), "unicode_escape")
        return decoded.strip()

    def _sanitize_payload(self, obj: Any, *, key_hint: str | None = None) -> Any:
        if isinstance(obj, dict):
            return {k: self._sanitize_payload(v, key_hint=k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize_payload(v) for v in obj]
        if isinstance(obj, str):
            if key_hint == "raw_log":
                obj = obj.replace('"', "'")
            return self._clean_codec_str(obj)
        return obj

    # ===========================
    # Generic CRUD
    # ===========================

    @with_connection
    def insert_one(self, collection: str, doc: dict, *, clean_codec: bool = False, mongo_db):
        payload = self._sanitize_payload(doc) if clean_codec else dict(doc)
        return mongo_db[collection].insert_one(payload).inserted_id

    @with_connection
    def insert_many(self, collection: str, docs: Iterable[dict], *, clean_codec: bool = False, mongo_db):
        payload = [self._sanitize_payload(d) if clean_codec else dict(d) for d in docs]
        return mongo_db[collection].insert_many(payload).inserted_ids

    @with_connection
    def upsert_one(self, collection: str, filter_query: dict, update_fields: dict, *, clean_codec: bool = False, mongo_db):
        fields = self._sanitize_payload(update_fields) if clean_codec else dict(update_fields)
        res = mongo_db[collection].update_one(filter_query, {"$set": fields}, upsert=True)
        return res.upserted_id

    @with_connection
    def find(self, collection: str, filter_query: dict, *, projection: dict | None = None, limit: int | None = None, mongo_db):
        cur = mongo_db[collection].find(filter_query, projection or None)
        if limit:
            cur = cur.limit(limit)
        return list(cur)

    @with_connection
    def find_sorted(self, collection: str, filter_query: dict, *, sort: list, limit: int | None = None, projection: dict | None = None, mongo_db):
        cur = mongo_db[collection].find(filter_query, projection).sort(sort)
        if limit:
            cur = cur.limit(limit)
        return list(cur)

    @with_connection
    def find_one(self, collection: str, filter_query: dict, *, projection: dict | None = None, mongo_db):
        return mongo_db[collection].find_one(filter_query, projection or None)

    # ===========================
    # Canonical Herringbone APIs
    # ===========================

    def insert_event(self, event: dict):
        return self.insert_one("events", event)

    def upsert_event_state(self, event_id, state: dict):
        state["last_updated"] = datetime.utcnow()
        return self.upsert_one("event_state", {"event_id": event_id}, state)

    def insert_parse_result(self, result: dict):
        return self.insert_one("parse_results", result)

    def insert_enrichment_result(self, result: dict):
        return self.insert_one("enrichment_results", result)

    def insert_detection(self, detection: dict):
        return self.insert_one("detections", detection)
