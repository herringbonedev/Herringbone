import hashlib

def resolve_ingestion_key(request, mongo):
    raw_key = request.headers.get("X-Herringbone-Key")

    if not raw_key:
        return None

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    try:
        record = mongo.find_one(
            "ingestion_keys",
            {
                "key_hash": key_hash,
                "enabled": True
            }
        )
    except Exception as e:
        print(f"[✗] ingestion key lookup failed: {e}")
        return None

    if not record:
        return None

    return record.get("context_id")