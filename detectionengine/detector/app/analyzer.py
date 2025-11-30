import os
import requests


MATCHER_URL = os.environ.get("MATCHER_API")


def analyze_log_with_rules(log_data: dict, rules: list[dict]) -> dict:
    """
    Sends the log + each rule to the MATCHER_API.
    Returns a combined detection summary.
    """
    if not MATCHER_URL:
        raise RuntimeError("MATCHER_API environment variable is not set.")

    results = []
    overall_detection = False

    for rule_entry in rules:
        matcher_rule = rule_entry.get("rule", {})

        payload = {
            "rule": matcher_rule,
            "log_data": log_data
        }

        response = requests.post(
            MATCHER_URL,
            json=payload,
            timeout=10
        )

        response.raise_for_status()
        match_result = response.json()

        matched = match_result.get("matched", False)

        results.append({
            "rule_name": rule_entry.get("name"),
            "severity": rule_entry.get("severity"),
            "description": rule_entry.get("description"),
            "matched": matched,
            "matcher_details": match_result.get("details"),
            "matcher_rule": matcher_rule,
        })

        if matched:
            overall_detection = True

    return {
        "detection": overall_detection,
        "details": results
    }
