MAX_LIMIT = 500
MAX_SCHEMA_SAMPLE = 50
MAX_SCHEMA_DEPTH = 4
MAX_ENUM_VALUES = 25

ALLOWED_COLLECTIONS = {
    "events",
    "event_state",
    "incidents",
    "detections",
    "parse_results",
    "enrichment_results",
}

SORTABLE_FIELDS = {
    "events": {"ingested_at", "_id"},
    "event_state": {"severity", "last_updated", "_id"},
    "detections": {"severity", "inserted_at", "_id"},
    "incidents": {"created_at", "updated_at", "priority", "_id"},
    "parse_results": {"parsed_at", "_id"},
    "enrichment_results": {"enriched_at", "_id"},
}

ALLOWED_OPERATORS = {
    "$gte",
    "$lte",
    "$gt",
    "$lt",
    "$eq",
    "$ne",
    "$in",
    "$nin",
    "$regex",
    "$and",
    "$or"
}
