from jsonschema import validate, ValidationError


class CardSchema:
    """Validates JSON data for a card entry supporting regex or jsonp definitions."""

    def __init__(self):
        selector_schema = {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                # Legacy/simple selectors use value. Path selectors may omit it
                # for exists/not_exists, and older clients may submit null.
                "value": {"type": ["string", "null"]},
                # Canonical field/path selector support.
                "path": {"type": ["string", "null"]},
                "field": {"type": ["string", "null"]},
                "match": {
                    "type": ["string", "null"],
                    "enum": [
                        "exact",
                        "contains",
                        "regex",
                        "exists",
                        "not_exists",
                        None,
                    ],
                },
            },
            "required": ["type"],
            "additionalProperties": True,
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "type": {
                                "enum": ["path", "field", "json", "jsonpath"]
                            }
                        }
                    },
                    "then": {
                        "anyOf": [
                            {"required": ["path"]},
                            {"required": ["field"]},
                        ]
                    },
                    "else": {
                        "required": ["value"]
                    },
                },
                {
                    "if": {
                        "properties": {
                            "match": {"enum": ["exact", "contains", "regex", None]}
                        }
                    },
                    "then": {
                        "properties": {
                            "value": {"type": "string"}
                        },
                        "required": ["value"]
                    },
                },
            ],
        }

        self.schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "selector": {
                    **selector_schema,
                    "properties": {
                        **selector_schema["properties"],
                        "not": {
                            "anyOf": [
                                selector_schema,
                                {"type": "array", "items": selector_schema},
                            ]
                        },
                        "and_not": {
                            "anyOf": [
                                selector_schema,
                                {"type": "array", "items": selector_schema},
                            ]
                        },
                        "excludes": {
                            "anyOf": [
                                selector_schema,
                                {"type": "array", "items": selector_schema},
                            ]
                        },
                        "exclude": {
                            "anyOf": [
                                selector_schema,
                                {"type": "array", "items": selector_schema},
                            ]
                        },
                    },
                },
                "regex": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "jsonp": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "required": ["selector"],
            "anyOf": [
                {"required": ["regex"]},
                {"required": ["jsonp"]},
            ],
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
