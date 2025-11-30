import re

class MatchEngine:

    def __call__(self, rule: dict, log: dict) -> bool:
        """
        Makes the instance callable like a function.
        """
        print(f"[*] Incoming log to match \n{str(log)} to rule \n{str(rule)}")
        return self.match(rule, log)

    def match(self, rule: dict, log: dict) -> bool:
        """
        Infers rule type based on keys and dispatches.
        """
        if "regex" in rule:
            print("[*] ReGex rule")
            return self._match_regex(rule, log)
        print("[✗] Could not find validrule type. \nValid types: [regex]")
        return {"is_matched":False, "details": "Could not find valid rule type. \nValid types: [regex]", "status":400}

    def _match_regex(self, rule: dict, log: dict) -> bool:
        """
        Regex rule matching.
        """
        regex = rule.get("regex")
        key_path = rule.get("key")

        value = log
        for part in key_path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                print("[✗] Something went wrong with jsonp key path")
                return {"is_matched":False, "details": "Something went wrong with jsonp key path", "status":400}

        if not isinstance(value, str):
            print("[✗] The value at the key is not type str")
            return {"is_matched":False, "details": "The value at the key is not type str", "status":400}

        try:
            print(f"[✓] matching completed successfully \nresult: {str(bool(re.search(regex, value)))}")
            return {"is_matched":bool(re.search(regex, value)), "details": "matching completed successfully", "status":200}
        except re.error:
            print("[✗] Something went wrong with jsonp key path")
            return {"is_matched":False, "details": "Something went wrong with jsonp key path", "status":500}