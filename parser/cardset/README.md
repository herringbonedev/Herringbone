# CardSet

The CardSet service functions as a key-value store for log parsing configurations. Each entry defines a selector that links a specific JSON-formatted dataset to its corresponding parsing relationship.

## Card Schema

```json
{
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
```

