import re
from typing import Any, Dict, List, Union
from jsonpath_ng import parse as jsonpath_parse


class CardParser:
    # Unified parser for CardSet extraction (regex or jsonp)

    def __init__(self, mode: str):
        valid_modes = {"regex", "jsonp"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")
        self.mode = mode

    def __call__(
        self,
        rules: List[Dict[str, str]],
        data: Union[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        if self.mode == "regex":
            return self._apply_regex(rules, str(data))
        if self.mode == "jsonp":
            return self._apply_jsonp(rules, data)
        raise RuntimeError(f"Unsupported mode: {self.mode}")

    def _apply_regex(
        self,
        regex_rules: List[Dict[str, str]],
        text: str,
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}

        for rule in regex_rules:
            for field, pattern in rule.items():
                try:
                    match = re.search(pattern, text, flags=re.IGNORECASE)
                    if not match:
                        continue

                    # Prefer capture groups, otherwise full match
                    if match.groups():
                        results[field] = match.group(1)
                    else:
                        results[field] = match.group(0)

                except re.error as e:
                    results[field] = f"[regex error: {e}]"

        return results

    def _apply_jsonp(
        self,
        jsonp_rules: List[Dict[str, str]],
        json_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}

        for rule in jsonp_rules:
            for field, path in rule.items():
                try:
                    expr = jsonpath_parse(path)
                    matches = [m.value for m in expr.find(json_data)]

                    # Normalize single vs multi-value paths
                    results[field] = matches[0] if len(matches) == 1 else matches

                except Exception as e:
                    results[field] = f"[jsonpath error: {e}]"

        return results
