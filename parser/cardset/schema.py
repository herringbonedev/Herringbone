from jsonschema import validate, ValidationError

class CardSchema:
    """Validates JSON data for a card entry supporting regex or jsonp definitions."""

    def __init__(self):
        self.schema = {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "value": {"type": "string"}
                    },
                    "required": ["type", "value"]
                },
                "regex": {
                    "type": "array",
                    "items": {"type": "object"}
                },
                "jsonp": {
                    "type": "array",
                    "items": {"type": "object"}
                }
            },
            "oneOf": [
                {"required": ["regex"]},
                {"required": ["jsonp"]}
            ],
            "required": ["selector"]
        }

    def __call__(self, data: dict) -> dict:
        """
        Allow instance to be called directly for validation.
        Example:
            validator = CardSchema()
            result = validator(data)
        """
        return self.validate(data)

    def validate(self, data: dict) -> dict:
        """
        Validate a JSON object against the Card schema.

        Returns:
            dict: { "valid": bool, "error": str or None }
        """
        try:
            validate(instance=data, schema=self.schema)
            return {"valid": True, "error": None}
        except ValidationError as e:
            return {"valid": False, "error": e.message}
