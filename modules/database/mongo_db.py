from functools import wraps
from pymongo import MongoClient, errors


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
    MongoDB wrapper with automatic connection handling and ergonomic updates.
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

    @with_connection
    def insert_log(self, doc: dict, *, mongo_coll):
        """Insert one document; return inserted _id as string."""
        res = mongo_coll.insert_one(doc)
        return str(res.inserted_id)

    @with_connection
    def clear_logs(self, *, mongo_coll):
        """Delete all docs in the collection; return deleted count."""
        return mongo_coll.delete_many({}).deleted_count

    @with_connection
    def drop_logs(self, *, mongo_db):
        """Drop the collection; return drop result."""
        return mongo_db.drop_collection(self.collection)

    @with_connection
    def update_log(self, filter_query: dict, update_fields: dict, *, mongo_coll):
        """
        Smart update (single doc):
        - Normal keys -> $set (update/add)
        - Insert-only keys -> pass {"$insertOnly": value} as the value,
          these go to $setOnInsert (only applied if an upsert inserts a new doc)

        Always uses upsert=True so you can create the doc if it doesn't exist.

        Returns: {"matched": int, "modified": int, "upserted_id": ObjectId|None}
        """
        set_ops = {}
        insert_only_ops = {}

        # Split incoming dict into $set and $setOnInsert buckets.
        for k, v in update_fields.items():
            if isinstance(v, dict) and set(v.keys()) == {"$insertOnly"}:
                insert_only_ops[k] = v["$insertOnly"]
            else:
                set_ops[k] = v

        update_doc = {}
        if set_ops:
            update_doc["$set"] = set_ops
        if insert_only_ops:
            update_doc["$setOnInsert"] = insert_only_ops

        # If the user passed an empty dict, no-op safely
        if not update_doc:
            return {"matched": 0, "modified": 0, "upserted_id": None}

        res = mongo_coll.update_one(filter_query, update_doc, upsert=True)
        return {
            "matched": res.matched_count,
            "modified": res.modified_count,
            "upserted_id": getattr(res, "upserted_id", None),
        }

    @with_connection
    def update_many(self, filter_query: dict, update_fields: dict, *, mongo_coll):
        """
        Smart bulk update (many docs):
        Same dictionary contract as update_log, but applies to all matches.
        Upsert behavior with update_many can be surprising; we DO NOT upsert here
        (MongoDB would insert at most one new doc anyway).
        """
        set_ops = {}
        insert_only_ops = {}

        for k, v in update_fields.items():
            if isinstance(v, dict) and set(v.keys()) == {"$insertOnly"}:
                insert_only_ops[k] = v["$insertOnly"]
            else:
                set_ops[k] = v

        update_doc = {}
        if set_ops:
            update_doc["$set"] = set_ops
        if insert_only_ops:
            update_doc["$setOnInsert"] = insert_only_ops

        if not update_doc:
            return {"matched": 0, "modified": 0}

        res = mongo_coll.update_many(filter_query, update_doc, upsert=False)
        return {"matched": res.matched_count, "modified": res.modified_count}
