import re
from typing import Any, Iterable

class MatchEngine:

    def __call__(self, rule: dict, log: dict) -> dict:
        print(f"[*] Incoming log to match\n{log}\n[*] Rule\n{rule}")
        return self.match(rule, log)

    def match(self, rule: dict, log: dict) -> dict:
        if "regex" in rule:
            print("[*] Regex rule detected")
            return self._match_regex(rule, log)

        return {
            "is_matched": False,
            "details": "Could not find valid rule type",
            "status": 400,
        }

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
        """
        Normalize value to iterable of strings.
        """
        if isinstance(value, str):
            return [value]

        if isinstance(value, list):
            return [v for v in value if isinstance(v, str)]

        return []

    def _match_regex(self, rule: dict, log: dict) -> dict:
        regex = rule.get("regex")
        key_path = rule.get("key")
        
        value = self._resolve_key_path(key_path, log)

        if value is None:
            print("[!] Key path not found, falling back to raw")
            value = log.get("raw")

        values = self._values_as_iterable(value)

        if not values:
            return {
                "is_matched": False,
                "details": "Resolved value is not a string or list of strings",
                "status": 400,
            }

        try:
            matched = any(re.search(regex, v) for v in values)

            print(f"[✓] Regex evaluated against {values}")
            print(f"[✓] Match result: {matched}")

            return {
                "is_matched": matched,
                "details": "Regex evaluated successfully",
                "status": 200,
            }

        except re.error as e:

            print(f"[✗] Error: {e}")
            
            return {
                "is_matched": False,
                "details": f"Regex error: {str(e)}",
                "status": 500,
            }