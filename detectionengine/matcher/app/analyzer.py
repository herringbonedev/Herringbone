import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter


MATCHER_URL = os.environ.get("MATCHER_API")
MATCHER_BATCH_URL = os.environ.get("MATCHER_BATCH_API")
SERVICE_TOKEN_PATH = "/run/secrets/service_token"
MATCH_WORKERS = int(os.environ.get("DETECTOR_MATCH_WORKERS", 8))
MATCHER_TIMEOUT = float(os.environ.get("MATCHER_TIMEOUT", 10))
USE_MATCHER_BATCH = os.environ.get("DETECTOR_USE_MATCHER_BATCH", "true").lower() == "true"
_SERVICE_TOKEN_CACHE = None
_SESSION = None


def _batch_url() -> str | None:
    if MATCHER_BATCH_URL:
        return MATCHER_BATCH_URL
    if not MATCHER_URL:
        return None
    # Default: same matcher service, batch endpoint.
    return MATCHER_URL.replace("/find_match", "/find_matches_batch")


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    s = requests.Session()
    pool_size = int(os.environ.get("MATCHER_HTTP_POOL_SIZE", max(32, MATCH_WORKERS * 4)))
    adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=0)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    _SESSION = s
    return _SESSION


def service_auth_headers():
    global _SERVICE_TOKEN_CACHE

    if _SERVICE_TOKEN_CACHE is not None:
        return {"Authorization": f"Bearer {_SERVICE_TOKEN_CACHE}"}

    try:
        with open(SERVICE_TOKEN_PATH, "r") as f:
            _SERVICE_TOKEN_CACHE = f.read().strip()
        return {"Authorization": f"Bearer {_SERVICE_TOKEN_CACHE}"}
    except Exception as e:
        print(f"[✗] Failed to read service token: {e}")
        return {}


def _hit_from_match(log_data: dict, rule_entry: dict, match: dict) -> dict | None:
    matched = bool(match.get("matched", False))
    if not matched:
        return None

    return {
        "rule_id": rule_entry.get("rule_id") or rule_entry.get("id") or rule_entry.get("name"),
        "rule_name": rule_entry.get("name"),
        "severity": rule_entry.get("severity"),
        "description": rule_entry.get("description"),
        "matched": matched,
        "matcher_details": match.get("details"),
        "matcher_rule": rule_entry.get("rule"),
        "correlate_on": rule_entry.get("correlate_on"),
    }


def _check_rule(log_data: dict, rule_entry: dict) -> dict | None:
    if not MATCHER_URL:
        raise RuntimeError("MATCHER_API environment variable is not set.")

    payload = {
        "rule": rule_entry.get("rule", {}),
        "log_data": log_data,
    }

    resp = _session().post(
        MATCHER_URL,
        json=payload,
        headers=service_auth_headers(),
        timeout=MATCHER_TIMEOUT,
    )
    resp.raise_for_status()
    return _hit_from_match(log_data, rule_entry, resp.json())


def _check_rules_batch(log_data: dict, rules: list[dict]) -> list[dict]:
    url = _batch_url()
    if not url:
        raise RuntimeError("MATCHER_API environment variable is not set.")

    items = []
    rule_by_id = {}
    for idx, rule_entry in enumerate(rules):
        item_id = str(idx)
        rule_by_id[item_id] = rule_entry
        items.append(
            {
                "item_id": item_id,
                "rule": rule_entry.get("rule", {}),
                "log_data": log_data,
            }
        )

    resp = _session().post(
        url,
        json={"items": items},
        headers=service_auth_headers(),
        timeout=float(os.environ.get("MATCHER_BATCH_TIMEOUT", max(MATCHER_TIMEOUT, 30))),
    )
    resp.raise_for_status()
    data = resp.json()
    batch_results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(batch_results, list):
        raise RuntimeError("Matcher batch API returned invalid result shape")

    hits = []
    for item in batch_results:
        item_id = str(item.get("item_id"))
        rule_entry = rule_by_id.get(item_id)
        if not rule_entry:
            continue
        hit = _hit_from_match(log_data, rule_entry, item)
        if hit:
            hits.append(hit)

    return hits


def analyze_log_with_rules(log_data: dict, rules: list[dict]) -> dict:
    if not MATCHER_URL:
        raise RuntimeError("MATCHER_API environment variable is not set.")

    if not rules:
        return {"detection": False, "details": []}

    if USE_MATCHER_BATCH:
        try:
            results = _check_rules_batch(log_data, rules)
            return {"detection": bool(results), "details": results}
        except Exception as e:
            if os.environ.get("DETECTOR_MATCHER_BATCH_FALLBACK", "true").lower() != "true":
                raise
            print(f"[✗] matcher batch failed, falling back to single-rule calls: {e}")

    # Fallback/safe path: original one-rule-at-a-time API.
    if len(rules) == 1 or MATCH_WORKERS <= 1:
        results = []
        for rule_entry in rules:
            hit = _check_rule(log_data, rule_entry)
            if hit:
                results.append(hit)
        return {"detection": bool(results), "details": results}

    results = []
    workers = max(1, min(MATCH_WORKERS, len(rules)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_check_rule, log_data, rule) for rule in rules]
        for future in as_completed(futures):
            hit = future.result()
            if hit:
                results.append(hit)

    return {"detection": bool(results), "details": results}
