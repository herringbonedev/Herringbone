import os
import requests


MATCHER_URL = os.environ.get("MATCHER_API")


def analyze_log_with_rules(log_data: dict, rules: list[dict]) -> dict:
	if not MATCHER_URL:
		raise RuntimeError("MATCHER_API environment variable is not set.")

	results = []
	detected = False

	for rule_entry in rules:
		payload = {
			"rule": rule_entry.get("rule", {}),
			"log_data": log_data,
		}

		resp = requests.post(MATCHER_URL, json=payload, timeout=10)
		resp.raise_for_status()
		match = resp.json()

		matched = bool(match.get("matched", False))
		if matched:
			detected = True

		results.append(
			{
				"rule_name": rule_entry.get("name"),
				"severity": rule_entry.get("severity"),
				"description": rule_entry.get("description"),
				"matched": matched,
				"matcher_details": match.get("details"),
				"matcher_rule": rule_entry.get("rule"),
			}
		)

	return {
		"detection": detected,
		"details": results,
	}
