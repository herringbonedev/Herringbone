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

                "rule_id": {"type": "string"},
                "rule_name": {"type": "string"},
                "created_at": {},
                "last_updated": {},
                "state": {"type": "object"},

                "detections": {"type": "array", "items": {"type": "string"}},
                "events": {"type": "array", "items": {"type": "string"}},
                "owner": {"type": ["string", "null"]},
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
        """
        Allow instance to be called directly for validation.
        """
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
