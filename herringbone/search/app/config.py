MAX_LIMIT = 500
MAX_SCHEMA_SAMPLE = 50
MAX_SCHEMA_DEPTH = 4
MAX_ENUM_VALUES = 25
MAX_IN_VALUES = 250
MAX_REGEX_LENGTH = 256

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
    "events": {"ingested_at", "event_time", "created_at", "timestamp", "_id"},
    "event_state": {"severity", "last_updated", "updated_at", "_id"},
    "detections": {"severity", "inserted_at", "created_at", "_id"},
    "incidents": {"created_at", "updated_at", "last_updated", "priority", "_id"},
    "parse_results": {"created_at", "parsed_at", "_id"},
    "incident_events": {"created_at", "_id"},
    "enrichment_results": {"created_at", "enriched_at", "_id"},
}

# Prefer the first field for sorting; use all fields for time-range filtering.
COLLECTION_TIME_FIELDS = {
    "events": ("ingested_at", "event_time", "created_at", "timestamp"),
    "event_state": ("last_updated", "updated_at", "created_at"),
    "detections": ("inserted_at", "created_at"),
    "incidents": ("created_at", "updated_at", "last_updated"),
    "parse_results": ("created_at", "parsed_at"),
    "incident_events": ("created_at",),
    "enrichment_results": ("created_at", "enriched_at"),
}

DATE_FIELD_NAMES = {
    "created_at",
    "updated_at",
    "last_updated",
    "inserted_at",
    "ingested_at",
    "event_time",
    "timestamp",
    "parsed_at",
    "enriched_at",
}

BLOCKED_QUERY_FIELDS = {
    "context_id",
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
    "$options",
    "$and",
    "$or",
}
