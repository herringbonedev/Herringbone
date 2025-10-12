import re
import json
from typing import Any, Dict, List, Union
from jsonpath_ng import parse as jsonpath_parse


class CardParser:
    """
    A unified parser that can operate in either 'regex' or 'jsonp' mode.
    - regex mode: takes a list of {name: pattern} and a string input
    - jsonp mode: takes a list of {name: jsonpath} and a dict input
    """

    def __init__(self, mode: str):
        valid_modes = {"regex", "jsonp"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")
        self.mode = mode

    def __call__(self, rules: List[Dict[str, str]], data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply the given rules to the input data.
        Returns a dict of extracted results: {field_name: matched_value or None}
        """
        if self.mode == "regex":
            return self._apply_regex(rules, str(data))
        elif self.mode == "jsonp":
            return self._apply_jsonp(rules, data)
        else:
            raise RuntimeError(f"Unsupported mode: {self.mode}")

    def _apply_regex(self, regex_rules: List[Dict[str, str]], text: str) -> Dict[str, Any]:
        results = {}
        for rule in regex_rules:
            for name, pattern in rule.items():
                try:
                    match = re.search(pattern, text, flags=re.IGNORECASE)
                    if match:
                        results[name] = match.group(1) if match.groups() else match.group(0)
                    else:
                        results[name] = None
                except re.error as e:
                    results[name] = f"[regex error: {e}]"
        return results

    def _apply_jsonp(self, jsonp_rules: List[Dict[str, str]], json_data: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        for rule in jsonp_rules:
            for name, path in rule.items():
                try:
                    expr = jsonpath_parse(path)
                    matches = [match.value for match in expr.find(json_data)]
                    results[name] = matches[0] if matches else None
                except Exception as e:
                    results[name] = f"[jsonpath error: {e}]"
        return results
