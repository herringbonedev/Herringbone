import hashlib
from typing import Optional


def normalize_ingestion_key(raw_key: Optional[str]) -> str:
    return (raw_key or "").strip()


def ingestion_key_hash(raw_key: str) -> str:
    return hashlib.sha256(normalize_ingestion_key(raw_key).encode("utf-8")).hexdigest()


def ingestion_key_hash_prefix(raw_key: str, length: int = 12) -> str:
    key = normalize_ingestion_key(raw_key)
    if not key:
        return ""
    return ingestion_key_hash(key)[:length]


def _enabled(value) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "enabled"}
    if isinstance(value, int):
        return value == 1
    return False


def resolve_ingestion_key_value(raw_key: Optional[str], mongo):
    """
    Resolve a raw hb_ingest_* key to a context_id.

    TCP/UDP receivers do not have an HTTP request object, so they should call
    this directly at startup and cache the returned context_id.
    """
    raw_key = normalize_ingestion_key(raw_key)
    if not raw_key:
        return None

    key_hash = ingestion_key_hash(raw_key)

    try:
        # Query by hash only, then validate enabled in Python. This gives the
        # same behavior as the previous {key_hash, enabled: True} query while
        # making disabled/malformed records easier to reason about.
        record = mongo.find_one("ingestion_keys", {"key_hash": key_hash})
    except Exception as e:
        print(f"[✗] ingestion key lookup failed: {e}", flush=True)
        return None

    if not record:
        print(
            f"[✗] ingestion key not found hash_prefix={key_hash[:12]}",
            flush=True,
        )
        return None

    if not _enabled(record.get("enabled")):
        print(
            f"[✗] ingestion key found but disabled hash_prefix={key_hash[:12]}",
            flush=True,
        )
        return None

    context_id = record.get("context_id")
    if not context_id:
        print(
            f"[✗] ingestion key found but missing context_id hash_prefix={key_hash[:12]}",
            flush=True,
        )
        return None

    return context_id


def resolve_ingestion_key(request, mongo):
    return resolve_ingestion_key_value(
        request.headers.get("X-Herringbone-Key"),
        mongo,
    )
