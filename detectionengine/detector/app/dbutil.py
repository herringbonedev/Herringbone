import os
from threading import Lock

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.database.mongo_bulk import HerringboneMongoBulkOperations


_MONGO_DB = None
_MONGO_BULK = None
_LOCK = Lock()


def mongo_db() -> HerringboneMongoDatabase:
    """
    Original working detector auth path, cached per process.

    Keep this intentionally simple. hbctl/compose already manages MONGO_* envs.
    Do not force AUTH_DB or raw pymongo behavior here.
    """
    global _MONGO_DB

    if _MONGO_DB is not None:
        return _MONGO_DB

    with _LOCK:
        if _MONGO_DB is None:
            _MONGO_DB = HerringboneMongoDatabase(
                user=os.environ.get("MONGO_USER", ""),
                password=os.environ.get("MONGO_PASS", ""),
                database=os.environ.get("DB_NAME", "herringbone"),
                host=os.environ.get("MONGO_HOST", "localhost"),
            )

    return _MONGO_DB


def mongo_bulk() -> HerringboneMongoBulkOperations:
    """
    Bulk wrapper using the same auth style as the old detector, cached per process.

    This avoids constructing HerringboneMongoBulkOperations on every polling loop.
    mongodb_bulk.py prints "BULK MONGO DB" in __init__, so repeated log spam means
    repeated wrapper construction.
    """
    global _MONGO_BULK

    if _MONGO_BULK is not None:
        return _MONGO_BULK

    with _LOCK:
        if _MONGO_BULK is None:
            _MONGO_BULK = HerringboneMongoBulkOperations(
                user=os.environ.get("MONGO_USER", ""),
                password=os.environ.get("MONGO_PASS", ""),
                database=os.environ.get("DB_NAME", "herringbone"),
                host=os.environ.get("MONGO_HOST", "localhost"),
            )

    return _MONGO_BULK


def close_mongo_clients():
    """
    Optional cleanup hook for tests/shutdown paths.
    """
    global _MONGO_DB, _MONGO_BULK

    with _LOCK:
        for client in (_MONGO_DB, _MONGO_BULK):
            if client is not None and hasattr(client, "close_mongo_connection"):
                try:
                    client.close_mongo_connection()
                except Exception:
                    pass

        _MONGO_DB = None
        _MONGO_BULK = None
