from jsonschema import validate, ValidationError


class IncidentSchema:
    """Validates JSON data for an incident entry."""

    def __init__(self):
        self.schema = {
            "type": "object",
            "required": [
                "title",
                "status",
                "priority",
            ],
            "additionalProperties": True,
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "description": {"type": "string"},

                "status": {
                    "type": "string",
                    "enum": ["open", "investigating", "resolved"],
                },

                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },

                # Context ID
                "context_id": {"type": "string"},

                # Rule metadata
                "rule_id": {"type": "string"},
                "rule_name": {"type": "string"},

                # Timestamps
                "created_at": {},
                "last_updated": {},

                # State object
                "state": {"type": "object"},

                # Related objects
                "detections": {
                    "type": "array",
                    "items": {"type": "string"},
                },

                "events": {
                    "type": "array",
                    "items": {"type": "string"},
                },

                "owner": {"type": ["string", "null"]},

                # Notes
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["author", "timestamp", "message"],
                        "properties": {
                            "author": {"type": "string"},
                            "timestamp": {},
                            "message": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        }

    def __call__(self, data: dict) -> dict:
        return self.validate(data)

    def validate(self, data: dict) -> dict:
        """
        Validate a JSON object against the Incident schema.

        Returns:
            dict: { "valid": bool, "error": str or None }
        """
        try:
            validate(instance=data, schema=self.schema)
            return {"valid": True, "error": None}

        except ValidationError as e:
            return {"valid": False, "error": e.message}