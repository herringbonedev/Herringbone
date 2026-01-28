"""
Herringbone liveness/readiness probes.

- livez(): basic process health
- readyz(): verifies Mongo connectivity using modules.database.mongo_db

Usage (manual):
  python container_probes.py readyz
  python container_probes.py livez
"""

from __future__ import annotations


import os
import sys
import json
from typing import Dict, Any

from modules.database.mongo_db import HerringboneMongoDatabase


class MongoNotSet(Exception):
    """Raised when required Mongo env vars are missing."""
    pass


def _get_mongo_from_env() -> HerringboneMongoDatabase:
    """
    Build the DB helper from environment variables.
    Requires: MONGO_HOST, DB_NAME, COLLECTION_NAME
    Optional: MONGO_USER, MONGO_PASS, MONGO_PORT, MONGO_AUTH_SOURCE, MONGO_REPLICA_SET
    """
    mongo_host = os.environ.get("MONGO_HOST")
    db_name = os.environ.get("DB_NAME")
    coll_name = os.environ.get("COLLECTION_NAME")

    if not mongo_host:
        raise MongoNotSet("MONGO_HOST is not set.")
    if not db_name:
        raise MongoNotSet("DB_NAME is not set.")
    if not coll_name:
        raise MongoNotSet("COLLECTION_NAME is not set.")

    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=db_name,
        collection=coll_name,
        host=mongo_host,
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("MONGO_AUTH_SOURCE", "admin"),
        replica_set=os.environ.get("MONGO_REPLICA_SET") or None,
    )


def readyz() -> Dict[str, Any]:
    """
    Readiness probe:
    - Instantiate helper from env
    - Open connection (does a ping internally)
    - Close connection
    Returns dict with readyz: bool and reason: str
    """
    try:
        mongo = _get_mongo_from_env()
    except MongoNotSet as e:
        return {"readyz": False, "reason": str(e)}
    except Exception as e:
        return {"readyz": False, "reason": f"Failed to read Mongo env: {e}"}

    try:
        client, db, coll = mongo.open_mongo_connection()  # ping happens inside
        return {"readyz": True, "reason": "MongoDB connection success"}
    except Exception as e:
        return {"readyz": False, "reason": f"Failed to connect to MongoDB: {e}"}
    finally:
        # Always attempt to close if it was opened
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass


def livez() -> Dict[str, Any]:
    """
    Liveness probe:
    - Lightweight; just confirms the process is responsive.
    """
    return {"livez": True, "reason": ""}


if __name__ == "__main__":
    # Simple CLI for manual testing
    if len(sys.argv) < 2:
        print("Usage: python container_probes.py [readyz|livez]")
        sys.exit(2)

    cmd = sys.argv[1].lower()
    if cmd == "readyz":
        print(json.dumps(readyz()))
    elif cmd == "livez":
        print(json.dumps(livez()))
    else:
        print("Unknown command. Use 'readyz' or 'livez'.")
        sys.exit(2)
