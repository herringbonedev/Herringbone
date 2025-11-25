from jsonschema import validate, ValidationError

class RuleSchema:
    """Validates JSON data for a rule entry supporting regex or jsonp definitions."""

    def __init__(self):
        self.schema = {
            "type": "object",
            "required": ["name", "severity", "description", "rule"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "severity": {"type": "integer", "minimum": 0, "maximum": 100},
                "description": {"type": "string"},
                "rule": {
                    "type": "object",
                    "required": ["key"],
                    "additionalProperties": False,
                    "properties": {
                        "key": {"type": "string", "minLength": 1},
                        "standard": {},
                        "regex": {"type": "string"}
                    },
                    "oneOf": [
                        {"required": ["standard"], "properties": {"standard": {}}},
                        {"required": ["regex"], "properties": {"regex": {"type": "string"}}}
                    ]
                }
            }
        }



    def __call__(self, data: dict) -> dict:
        """
        Allow instance to be called directly for validation.
        Example:
            validator = RuleSchema()
            result = validator(data)
        """
        return self.validate(data)

    def validate(self, data: dict) -> dict:
        """
        Validate a JSON object against the Rule schema.

        Returns:
            dict: { "valid": bool, "error": str or None }
        """
        try:
            validate(instance=data, schema=self.schema)
            print("Valid JSON")
            return {"valid": True, "error": None}
        except ValidationError as e:
            print("Invalid JSON")
            return {"valid": False, "error": e.message}
