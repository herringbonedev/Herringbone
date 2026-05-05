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
    "incident_events",
    "enrichment_results",
}

SORTABLE_FIELDS = {
    "events": {"ingested_at", "event_time", "_id"},
    "event_state": {"severity", "last_updated", "_id"},
    "detections": {"severity", "inserted_at", "_id"},
    "incidents": {"created_at", "updated_at", "last_updated", "priority", "_id"},
    "parse_results": {"created_at", "parsed_at", "_id"},
    "incident_events": {"created_at", "_id"},
    "enrichment_results": {"created_at", "enriched_at", "_id"},
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
