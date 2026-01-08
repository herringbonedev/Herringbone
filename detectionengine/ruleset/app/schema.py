from jsonschema import validate, ValidationError

class RuleSchema:
    def __init__(self):
        self.schema = {
            "type": "object",
            "required": ["name", "severity", "description", "rule"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "severity": {"type": "integer", "minimum": 0, "maximum": 100},
                "description": {"type": "string"},
                "correlate_on": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "minLength": 1
                    },
                    "uniqueItems": True
                },
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
                        {
                            "required": ["standard"],
                            "properties": {"standard": {}}
                        },
                        {
                            "required": ["regex"],
                            "properties": {"regex": {"type": "string"}}
                        }
                    ]
                }
            }
        }

    def __call__(self, data: dict) -> dict:
        return self.validate(data)

    def validate(self, data: dict) -> dict:
        try:
            validate(instance=data, schema=self.schema)
            return {"valid": True, "error": None}
        except ValidationError as e:
            return {"valid": False, "error": e.message}
