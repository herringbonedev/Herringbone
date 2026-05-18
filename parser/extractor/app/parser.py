import re
from functools import lru_cache
from typing import Any, Dict, List, Union

from jsonpath_ng import parse as jsonpath_parse


@lru_cache(maxsize=8192)
def _compile_regex(pattern: str):
    return re.compile(pattern, flags=re.IGNORECASE)


@lru_cache(maxsize=4096)
def _compile_jsonpath(path: str):
    return jsonpath_parse(path)


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
                    compiled = _compile_regex(pattern)
                    match = compiled.search(text)
                    if not match:
                        continue

                    # Prefer capture groups, otherwise full match.
                    if match.groups():
                        results[field] = match.group(1)
                    else:
                        results[field] = match.group(0)

                except re.error as e:
                    results[field] = f"[regex error: {e}]"
                except Exception as e:
                    results[field] = f"[regex parser error: {e}]"

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
                    expr = _compile_jsonpath(path)
                    matches = [m.value for m in expr.find(json_data)]

                    # Normalize single vs multi-value paths.
                    results[field] = matches[0] if len(matches) == 1 else matches

                except Exception as e:
                    results[field] = f"[jsonpath error: {e}]"

        return results
