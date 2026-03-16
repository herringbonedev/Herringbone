def resolve_ingestion_key(request, mongo):
    auth = request.headers.get("Authorization")

    if not auth:
        return None

    auth = auth.strip()

    if not auth.lower().startswith("bearer "):
        return None

    token = auth[7:].strip()

    if not token:
        return None

    key_doc = mongo.find_one(
        "ingestion_keys",
        {
            "key": token,
            "enabled": True,
        }
    )

    if not key_doc:
        return None

    context_id = key_doc.get("context_id")

    if not context_id:
        return None

    return context_id