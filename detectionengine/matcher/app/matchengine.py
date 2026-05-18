import os
import re
from functools import lru_cache
from typing import Any, Iterable


DEBUG_MATCHER = os.environ.get("MATCHER_DEBUG", "false").lower() == "true"
REGEX_CACHE_SIZE = int(os.environ.get("MATCHER_REGEX_CACHE_SIZE", 4096))


@lru_cache(maxsize=REGEX_CACHE_SIZE)
def _compile_regex(pattern: str):
    return re.compile(pattern)


class MatchEngine:
    def __call__(self, rule: dict, log: dict) -> dict:
        if DEBUG_MATCHER:
            print(f"[*] Incoming log to match\n{log}\n[*] Rule\n{rule}")
        return self.match(rule, log)

    def match(self, rule: dict, log: dict) -> dict:
        if "regex" in rule:
            return self._match_regex(rule, log)

        return {
            "is_matched": False,
            "details": "Could not find valid rule type",
            "status": 400,
        }

    def match_many(self, items: list[dict]) -> list[dict]:
        results = []
        for idx, item in enumerate(items):
            item_id = item.get("item_id", idx)
            rule = item.get("rule") or {}
            log_data = item.get("log_data") or {}
            try:
                result = self.match(rule, log_data)
                results.append(
                    {
                        "item_id": item_id,
                        "matched": bool(result.get("is_matched")),
                        "details": result.get("details", ""),
                        "status": int(result.get("status", 200)),
                        "rule": rule,
                        "log_data": log_data,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "item_id": item_id,
                        "matched": False,
                        "details": str(e),
                        "status": 500,
                        "rule": rule,
                        "log_data": log_data,
                    }
                )
        return results

    def _resolve_key_path(self, key_path: str, log: dict) -> Any:
        if not key_path:
            return None

        parts = [p for p in key_path.strip(".").split(".") if p]

        value: Any = log
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None

        return value

    def _values_as_iterable(self, value: Any) -> Iterable[str]:
        if isinstance(value, str):
            return [value]

        if isinstance(value, list):
            return [v for v in value if isinstance(v, str)]

        return []

    def _match_regex(self, rule: dict, log: dict) -> dict:
        regex = rule.get("regex")
        key_path = rule.get("key")

        if not regex:
            return {
                "is_matched": False,
                "details": "Missing regex",
                "status": 400,
            }

        value = self._resolve_key_path(key_path, log)

        if value is None:
            value = log.get("raw")

        values = self._values_as_iterable(value)

        if not values:
            return {
                "is_matched": False,
                "details": "Resolved value is not a string or list of strings",
                "status": 400,
            }

        try:
            safe_pattern = re.escape(str(regex))
            compiled = _compile_regex(safe_pattern)
            matched = any(compiled.search(v) for v in values)

            return {
                "is_matched": matched,
                "details": "Regex evaluated successfully",
                "status": 200,
            }

        except re.error as e:
            return {
                "is_matched": False,
                "details": f"Regex error: {str(e)}",
                "status": 500,
            }
