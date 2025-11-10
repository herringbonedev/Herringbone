# modules/database/mongo_db.py

"""
Herringbone MongoDB helper module.

Features:
- Safe URI builder (percent-encodes username/password; IPv6 host bracketing).
- Connection decorator that opens, injects needed handles, and closes cleanly.
- Optional `clean_codec` flag for insert/update:
    * For any string: decode unicode escapes twice and strip.
    * For 'raw_log' key specifically: replace double quotes with single quotes
      before decoding (to keep prior ingestion semantics).
- Ergonomic updates:
    * Normal keys -> $set
    * Insert-only keys -> {"$insertOnly": value} -> $setOnInsert
"""

from __future__ import annotations

import inspect
import ipaddress
from urllib.parse import quote_plus
from functools import wraps
from typing import Any, Dict, Tuple
import codecs

from pymongo import MongoClient, errors


# --------------------------- Decorator ---------------------------

def with_connection(method):
    """
    Open/close a MongoDB connection around DB methods.

    This decorator introspects the target method and *only* injects the kwargs
    that it actually declares. Supported injectable names:
      - mongo_client
      - mongo_db
      - mongo_coll
    """
    sig = inspect.signature(method)
    params = set(sig.parameters.keys())

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            client, db, coll = self.open_mongo_connection()

            if "mongo_client" in params and "mongo_client" not in kwargs:
                kwargs["mongo_client"] = client
            if "mongo_db" in params and "mongo_db" not in kwargs:
                kwargs["mongo_db"] = db
            if "mongo_coll" in params and "mongo_coll" not in kwargs:
                kwargs["mongo_coll"] = coll

            return method(self, *args, **kwargs)

        except errors.PyMongoError as e:
            # Normalize PyMongo exceptions
            raise RuntimeError(f"MongoDB operation failed: {e}") from e
        finally:
            self.close_mongo_connection()

    return wrapper


# --------------------------- Helpers ---------------------------

def _fmt_host(host: str) -> str:
    """
    If host is an IPv6 literal, bracket it per RFC 2732.
    Otherwise return as-is.
    """
    try:
        ip = ipaddress.ip_address(host)
        return f"[{host}]" if ip.version == 6 else host
    except ValueError:
        # Not a pure IP literal (likely hostname/FQDN)
        return host


def _split_host_port_if_present(host: str) -> Tuple[str, int | None]:
    """
    Accepts strings like:
      - "db.example.com"
      - "db.example.com:27017"
      - "[2001:db8::1]:27017"
      - "2001:db8::1" (IPv6 literal without brackets)
    Returns (host_without_port, port_or_None). Host is *not* bracketed here.
    """
    h = host.strip()
    if not h:
        return h, None

    # If bracketed IPv6 with optional :port
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

    # If contains a single ":" and is likely host:port (not IPv6)
    if ":" in h and h.count(":") == 1:
        left, right = h.split(":", 1)
        try:
            return left, int(right)
        except ValueError:
            return h, None

    # Might be raw IPv6 literal without brackets or plain hostname
    return h, None


# --------------------------- Main Class ---------------------------

class HerringboneMongoDatabase:
    """
    MongoDB wrapper with automatic connection handling, optional codec cleaning,
    and ergonomic update helpers ($set + $setOnInsert via {"$insertOnly": value}).
    """

    def __init__(
        self,
        user: str,
        password: str,
        database: str,
        collection: str,
        host: str,
        port: int = 27017,
        auth_source: str = "herringbone",
        replica_set: str | None = "rs0",
    ):
        """
        Build a safe MongoDB URI:
          - Credentials are percent-encoded
          - IPv6 hosts are bracketed
          - Optional replica set parameters are appended
        """
        # If someone passed "host:port" in host, split it and let an explicit `port`
        # override only if the split didn't produce one.
        host_only, parsed_port = _split_host_port_if_present(host)
        port_final = parsed_port if parsed_port is not None else port

        user_enc = quote_plus(user) if user else ""
        pass_enc = quote_plus(password) if password else ""
        auth_block = f"{user_enc}:{pass_enc}@" if (user_enc or pass_enc) else ""

        qp = f"?authSource={quote_plus(auth_source)}"
        if replica_set:
            qp += f"&replicaSet={quote_plus(replica_set)}&readPreference=primary&directConnection=false"

        host_fmt = _fmt_host(host_only)
        self.uri = f"mongodb://{auth_block}{host_fmt}:{port_final}/{quote_plus(database)}{qp}"

        self.database = database
        self.collection = collection

        # Internal handles
        self.client: MongoClient | None = None
        self.db = None
        self.coll = None

    # ---------- Connection mgmt ----------

    def open_mongo_connection(self):
        """
        Connect and validate with a ping; return (client, db, coll).
        Raises RuntimeError with helpful messages if connection/auth fails.
        """
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,  # fail fast if unreachable
                retryWrites=True,
            )
            # Validate connection immediately
            self.client.admin.command("ping")

            self.db = self.client[self.database]
            self.coll = self.db[self.collection]
            return self.client, self.db, self.coll

        except errors.ServerSelectionTimeoutError as e:
            raise RuntimeError(f"MongoDB server unreachable: {e}") from e
        except errors.OperationFailure as e:
            raise RuntimeError(f"MongoDB authentication/operation failed: {e}") from e

    def close_mongo_connection(self):
        """Close client and clear handles."""
        if self.client:
            try:
                self.client.close()
            finally:
                self.client = None
                self.db = None
                self.coll = None

    # ---------- Cleaning helpers ----------

    @staticmethod
    def _clean_codec_str(value: str) -> str:
        """
        Apply clean_codec behavior to a string:
        - Decode unicode escapes (twice)
        - Strip whitespace
        """
        if not isinstance(value, str):
            return value
        decoded = value.encode("utf-8").decode("unicode_escape")
        decoded = codecs.decode(decoded.encode("utf-8"), "unicode_escape")
        return decoded.strip()

    def _sanitize_payload(self, obj: Any, *, key_hint: str | None = None) -> Any:
        """
        Recursively sanitize dictionaries/lists/scalars:
        - If key is 'raw_log', replace double quotes with single quotes first,
          then run codec cleaning.
        - For any plain string, run codec cleaning.
        - Preserve nested structures and non-string types as-is.
        - If a value is {"$insertOnly": x}, sanitize x as well.
        """
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                if isinstance(v, dict) and set(v.keys()) == {"$insertOnly"}:
                    inner = v["$insertOnly"]
                    out[k] = {"$insertOnly": self._sanitize_payload(inner, key_hint=k)}
                else:
                    out[k] = self._sanitize_payload(v, key_hint=k)
            return out

        if isinstance(obj, list):
            return [self._sanitize_payload(v) for v in obj]

        if isinstance(obj, str):
            if key_hint == "raw_log":
                obj = obj.replace('"', "'")
            return self._clean_codec_str(obj)

        # Other scalar types
        return obj

    # ---------- CRUD ops ----------

    @with_connection
    def delete_one(self, filter_query: dict, *, mongo_coll):
        """
        Delete a single document matching filter_query.

        Returns: {"deleted": int}
        """
        res = mongo_coll.delete_one(filter_query)
        return {"deleted": res.deleted_count}

    @with_connection
    def delete_many(self, filter_query: dict, *, mongo_coll):
        """
        Delete all documents matching filter_query.

        Returns: {"deleted": int}
        """
        res = mongo_coll.delete_many(filter_query)
        return {"deleted": res.deleted_count}
    
    @with_connection
    def delete_cards_by_selector(self, sel_type: str, sel_value: str, *, mongo_coll):
        """
        Delete all cards where selector.type == sel_type and selector.value == sel_value.

        Returns: {"deleted": int}
        """
        q = {"selector.type": sel_type, "selector.value": sel_value}
        res = mongo_coll.delete_many(q)
        return {"deleted": res.deleted_count}

    @with_connection
    def insert_log(self, doc: dict, *, clean_codec: bool = False, mongo_coll):
        """
        Insert one document; return inserted _id as string.

        :param doc: the document to insert
        :param clean_codec: when True, sanitize strings (including raw_log) before insert
        """
        payload = self._sanitize_payload(doc) if clean_codec else dict(doc)
        res = mongo_coll.insert_one(payload)
        return str(res.inserted_id)

    @with_connection
    def update_log(self, filter_query: dict, update_fields: dict, *, clean_codec: bool = False, mongo_coll):
        """
        Smart update (single doc):
        - Normal keys -> $set (update/add; creates fields if missing)
        - Insert-only keys -> pass {"$insertOnly": value} -> $setOnInsert
          (applied only if upsert inserts a new doc)
        - When clean_codec=True, sanitize strings in both buckets.

        Always uses upsert=True so the document can be created if missing.

        Returns: {"matched": int, "modified": int, "upserted_id": ObjectId|None}
        """
        fields = self._sanitize_payload(update_fields) if clean_codec else dict(update_fields)

        set_ops: Dict[str, Any] = {}
        insert_only_ops: Dict[str, Any] = {}

        for k, v in fields.items():
            if isinstance(v, dict) and set(v.keys()) == {"$insertOnly"}:
                insert_only_ops[k] = v["$insertOnly"]
            else:
                set_ops[k] = v

        update_doc: Dict[str, Any] = {}
        if set_ops:
            update_doc["$set"] = set_ops
        if insert_only_ops:
            update_doc["$setOnInsert"] = insert_only_ops

        if not update_doc:
            return {"matched": 0, "modified": 0, "upserted_id": None}

        res = mongo_coll.update_one(filter_query, update_doc, upsert=True)
        return {
            "matched": res.matched_count,
            "modified": res.modified_count,
            "upserted_id": getattr(res, "upserted_id", None),
        }

    @with_connection
    def update_many(self, filter_query: dict, update_fields: dict, *, clean_codec: bool = False, mongo_coll):
        """
        Smart bulk update (many docs):
        - Same dict contract as update_log.
        - No upsert here (Mongo would insert at most one doc anyway).

        Returns: {"matched": int, "modified": int}
        """
        fields = self._sanitize_payload(update_fields) if clean_codec else dict(update_fields)

        set_ops: Dict[str, Any] = {}
        insert_only_ops: Dict[str, Any] = {}

        for k, v in fields.items():
            if isinstance(v, dict) and set(v.keys()) == {"$insertOnly"}:
                insert_only_ops[k] = v["$insertOnly"]
            else:
                set_ops[k] = v

        update_doc: Dict[str, Any] = {}
        if set_ops:
            update_doc["$set"] = set_ops
        if insert_only_ops:
            update_doc["$setOnInsert"] = insert_only_ops

        if not update_doc:
            return {"matched": 0, "modified": 0}

        res = mongo_coll.update_many(filter_query, update_doc, upsert=False)
        return {"matched": res.matched_count, "modified": res.modified_count}

    @with_connection
    def clear_logs(self, *, mongo_coll):
        """
        Delete all documents from the collection.
        Returns number of deleted documents.
        """
        return mongo_coll.delete_many({}).deleted_count

    @with_connection
    def drop_logs(self, *, mongo_db):
        """
        Drop the entire collection.
        Returns drop result.
        """
        return mongo_db.drop_collection(self.collection)
    
    # ---------- Search ----------
    
    @with_connection
    def find(self, filter_query: dict, *, projection: dict | None = None, limit: int | None = None, mongo_coll):
        """
        Return a list of documents matching filter_query.
        """
        cur = mongo_coll.find(filter_query, projection or None)
        if isinstance(limit, int) and limit > 0:
            cur = cur.limit(limit)
        return list(cur)

    @with_connection
    def find_one(self, filter_query: dict, *, projection: dict | None = None, mongo_coll):
        """
        Return a single document or None.
        """
        return mongo_coll.find_one(filter_query, projection or None)

    @with_connection
    def ensure_selector_index(self, *, mongo_coll):
        """
        Create an index to speed up selector lookups.
        """
        return mongo_coll.create_index(
            [("selector.type", 1), ("selector.value", 1)],
            name="selector_type_value_idx"
        )
    
    @with_connection
    def find_cards_by_selector(self, sel_type: str, sel_value: str, *, limit: int | None = None, projection: dict | None = None, mongo_coll):
        """
        Find cards where selector.type == sel_type and selector.value == sel_value.
        """
        q = {"selector.type": sel_type, "selector.value": sel_value}
        cur = mongo_coll.find(q, projection or None)
        if isinstance(limit, int) and limit > 0:
            cur = cur.limit(limit)
        return list(cur)
    
    @with_connection
    def find_all_cards(self, *, limit: int | None = None, projection: dict | None = None, mongo_coll):
        """
        Return all cards in the collection.
        """
        cur = mongo_coll.find({}, projection or None)
        if isinstance(limit, int) and limit > 0:
            cur = cur.limit(limit)
        return list(cur)
