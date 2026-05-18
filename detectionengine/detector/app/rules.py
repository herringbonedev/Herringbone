import os
from time import time

from app.dbutil import mongo_db


RULE_RELOAD_INTERVAL = float(os.environ.get("RULE_RELOAD_INTERVAL", 30))
_rules_cache: dict[str, list[dict]] = {}
_rules_last_load: dict[str, float] = {}


def load_rules(context_id: str) -> list[dict]:
    if not context_id:
        return []

    now = time()
    cached = _rules_cache.get(context_id)
    last = _rules_last_load.get(context_id, 0)
    if cached is not None and now - last < RULE_RELOAD_INTERVAL:
        return cached

    rules_collection = os.environ.get("RULES_COLLECTION_NAME", "rules")
    mongo = mongo_db()

    try:
        items = mongo.find_with_context(rules_collection, {}, context_id=context_id)
    except Exception as e:
        print(f"[✗] failed to load rules: {e}")
        items = []

    for rule in items:
        rule.pop("_id", None)

    _rules_cache[context_id] = items
    _rules_last_load[context_id] = now
    return items
