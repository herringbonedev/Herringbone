from jsonschema import validate, ValidationError


class CardSchema:
    """Validates JSON data for a card entry supporting regex or jsonp definitions."""

    def __init__(self):
        selector_schema = {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "value": {"type": "string"},

                # Structured selector fields. These allow enrichment to match
                # against event/fingerprint fields instead of raw text only.
                # Examples:
                #   {"type":"jsonpath", "path":"$.fingerprint.source_name", "match":"exact", "value":"Cloudflare"}
                #   {"type":"field", "field":"fingerprint.source_name", "match":"regex", "value":"(?i)^cloudflare$"}
                "field": {"type": "string"},
                "path": {"type": "string"},
                "jsonpath": {"type": "string"},
                "key": {"type": "string"},
                "match": {
                    "type": "string",
                    "enum": [
                        "exact", "eq", "equals", "==",
                        "regex", "matches", "re",
                        "contains", "substring", "in",
                        "not_equals", "ne", "!=", "not_exact",
                        "not_regex", "not_matches",
                    ],
                },
                "operator": {"type": "string"},
                "compare": {"type": "string"},
            },
            "required": ["type", "value"],
            "additionalProperties": True,
        }

        self.schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string"
                },
                "selector": {
                    **selector_schema,
                    "properties": {
                        **selector_schema["properties"],
                        "not": {
                            "anyOf": [
                                selector_schema,
                                {
                                    "type": "array",
                                    "items": selector_schema,
                                }
                            ]
                        },
                        "and_not": {
                            "anyOf": [
                                selector_schema,
                                {
                                    "type": "array",
                                    "items": selector_schema,
                                }
                            ]
                        },
                        "exclude": {
                            "anyOf": [
                                selector_schema,
                                {
                                    "type": "array",
                                    "items": selector_schema,
                                }
                            ]
                        },
                        "excludes": {
                            "anyOf": [
                                selector_schema,
                                {
                                    "type": "array",
                                    "items": selector_schema,
                                }
                            ]
                        },
                    },
                },
                "regex": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    }
                },
                "jsonp": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    }
                }
            },
            "required": ["selector"],
            "anyOf": [
                {"required": ["regex"]},
                {"required": ["jsonp"]}
            ]
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
