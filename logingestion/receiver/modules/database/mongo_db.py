from functools import wraps
from pymongo import MongoClient, errors
from datetime import datetime
import codecs
from typing import Any, Dict


def with_connection(method):
    """
    Decorator to open/close a MongoDB connection around DB methods.
    Injects mongo_client, mongo_db, mongo_coll as keyword-only params.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            client, db, coll = self.open_mongo_connection()
            kwargs.setdefault("mongo_client", client)
            kwargs.setdefault("mongo_db", db)
            kwargs.setdefault("mongo_coll", coll)
            return method(self, *args, **kwargs)
        except errors.PyMongoError as e:
            # Normalize PyMongo errors to a clear RuntimeError
            raise RuntimeError(f"MongoDB operation failed: {e}") from e
        finally:
            self.close_mongo_connection()
    return wrapper


class HerringboneMongoDatabase:
    """
    MongoDB wrapper with automatic connection handling, optional codec cleaning,
    and ergonomic update helpers ($set + $setOnInsert via {"$insertOnly": value}).
    """

    def __init__(self, user, password, database, collection, host, port=27017,
                 auth_source="herringbone", replica_set="rs0"):
        # Build URI with authSource and optional replica set params
        qp = f"?authSource={auth_source}"
        if replica_set:
            qp += f"&replicaSet={replica_set}&readPreference=primary&directConnection=false"
        self.uri = f"mongodb://{user}:{password}@{host}:{port}/{database}{qp}"

        self.database = database
        self.collection = collection
        self.client = self.db = self.coll = None

    # ---------- Connection mgmt ----------

    def open_mongo_connection(self):
        """
        Connect and validate with a ping; return (client, db, coll).
        """
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000, retryWrites=True)
            self.client.admin.command("ping")  # fail fast if unreachable
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
            self.client.close()
            self.client = self.db = self.coll = None

    # ---------- Cleaning helpers ----------

    @staticmethod
    def _clean_codec_str(value: str) -> str:
        """
        Apply legacy clean_codec behavior to a string:
        - Decode unicode escapes (twice, as in original)
        - Strip whitespace
        """
        # Guard against accidental non-str inputs
        if not isinstance(value, str):
            return value
        decoded = value.encode("utf-8").decode("unicode_escape")
        decoded = codecs.decode(decoded.encode("utf-8"), "unicode_escape")
        return decoded.strip()

    def _sanitize_payload(self, obj: Any, *, key_hint: str | None = None) -> Any:
        """
        Recursively sanitize dictionaries/lists/scalars:
        - If key looks like 'raw_log', replace double quotes with single quotes first
          (to mirror old behavior), then run codec cleaning.
        - For any plain string, run codec cleaning.
        - Preserve nested structures and non-string types as-is.
        """
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                # Handle {"$insertOnly": <value>} passthrough sentinel by cleaning its value too
                if isinstance(v, dict) and set(v.keys()) == {"$insertOnly"}:
                    inner = v["$insertOnly"]
                    out[k] = {"$insertOnly": self._sanitize_payload(inner, key_hint=k)}
                else:
                    out[k] = self._sanitize_payload(v, key_hint=k)
            return out

        if isinstance(obj, list):
            return [self._sanitize_payload(v) for v in obj]

        if isinstance(obj, str):
            # Special-case: raw_log should replace " with ' before decoding (legacy behavior)
            if key_hint == "raw_log":
                obj = obj.replace('"', "'")
            return self._clean_codec_str(obj)

        # For all other scalar types, return unchanged
        return obj

    # ---------- CRUD ops ----------

    @with_connection
    def insert_log(self, doc: dict, *, clean_codec: bool = False, mongo_coll):
        """
        Insert one document; return inserted _id as string.

        :param doc: the document to insert
        :param clean_codec: when True, sanitize strings (including raw_log) before insert
        """
        payload = self._sanitize_payload(doc) if clean_codec else dict(doc)

        # Optionally set default fields if they are missing (keeps your legacy defaults)
        payload.setdefault("recon", False)
        payload.setdefault("detected", False)
        payload.setdefault("recon_data", None)
        payload.setdefault("last_update", datetime.utcnow())

        res = mongo_coll.insert_one(payload)
        return str(res.inserted_id)

    @with_connection
    def update_log(self, filter_query: dict, update_fields: dict, *,
                   clean_codec: bool = False, mongo_coll):
        """
        Smart update (single doc):
        - Normal keys -> $set (update/add; also creates fields if missing)
        - Insert-only keys -> pass {"$insertOnly": value}, routed to $setOnInsert
          (applied only if upsert inserts a new doc)
        - When clean_codec=True, sanitize strings in both buckets.

        Always uses upsert=True so doc can be created if it doesn't exist.

        Returns: {"matched": int, "modified": int, "upserted_id": ObjectId|None}
        """
        # Optionally sanitize the incoming fields first (preserves $insertOnly sentinel)
        fields = self._sanitize_payload(update_fields) if clean_codec else dict(update_fields)

        set_ops = {}
        insert_only_ops = {}

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
    def update_many(self, filter_query: dict, update_fields: dict, *,
                    clean_codec: bool = False, mongo_coll):
        """
        Smart bulk update (many docs):
        - Same dict contract as update_log.
        - We do NOT upsert here (Mongo would insert at most one new doc anyway).

        Returns: {"matched": int, "modified": int}
        """
        fields = self._sanitize_payload(update_fields) if clean_codec else dict(update_fields)

        set_ops = {}
        insert_only_ops = {}

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
