from fastapi import HTTPException

from app.query_parser import parse_q_string
from app.filters import build_range_filters
from datetime import datetime
from bson import ObjectId

from app.pagination import coerce_after, apply_after
from app.serializer import serialize
from app.config import SORTABLE_FIELDS, MAX_ENUM_VALUES


def mongo_database(mongo):
    """Return the PyMongo database using the public Mongo wrapper API."""
    _, db = mongo.open_mongo_connection()
    return db


def with_context_filter(filter_query, context_id: str):
    query = dict(filter_query or {})
    if context_id:
        query["context_id"] = context_id
    return query


def search_collection_service(mongo, collection, params, context_id: str):
    filter_query = parse_q_string(params.q)

    sort_field = params.sort or "_id"
    if sort_field not in SORTABLE_FIELDS.get(collection, set()):
        raise HTTPException(400, "Sorting by this field is not allowed")

    after_oid = coerce_after(params.after)
    if after_oid and sort_field != "_id":
        raise HTTPException(400, "Cursor pagination is only supported when sorting by _id")

    filter_query = build_range_filters(
        collection=collection,
        filter_query=filter_query,
        severity_min=params.severity_min,
        severity_max=params.severity_max,
        from_ts=params.from_ts,
        to_ts=params.to_ts,
        filter_field=params.filter_field,
        filter_kind=params.filter_kind,
        filter_min=params.filter_min,
        filter_max=params.filter_max,
        filter_in=params.filter_in,
        filter_value=params.filter_value,
    )

    filter_query = apply_after(filter_query, after_oid, params.order)

    sort_dir = 1 if params.order == "asc" else -1

    results = mongo.find_sorted_with_context(
        collection=collection,
        filter_query=filter_query,
        context_id=context_id,
        sort=[(sort_field, sort_dir)],
        limit=params.limit,
    )

    results = serialize(results)

    next_after = None
    if results and len(results) == params.limit:
        last = results[-1]
        if isinstance(last, dict) and "_id" in last:
            next_after = last["_id"]

    return results, next_after



def count_collection_service(mongo, collection, params, context_id: str):
    filter_query = parse_q_string(params.q)

    filter_query = build_range_filters(
        collection=collection,
        filter_query=filter_query,
        severity_min=params.severity_min,
        severity_max=params.severity_max,
        from_ts=params.from_ts,
        to_ts=params.to_ts,
        filter_field=params.filter_field,
        filter_kind=params.filter_kind,
        filter_min=params.filter_min,
        filter_max=params.filter_max,
        filter_in=params.filter_in,
        filter_value=params.filter_value,
    )

    db = mongo_database(mongo)
    return db[collection].count_documents(with_context_filter(filter_query, context_id))

def _field_type(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, datetime):
        return "date"
    if isinstance(value, ObjectId):
        return "objectid"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "string"


def _add_sample(stats, path, value):
    entry = stats.setdefault(path, {"types": set(), "enum": set(), "enum_closed": False})
    entry["types"].add(_field_type(value))

    if isinstance(value, (str, int, float, bool)) and not entry["enum_closed"]:
        entry["enum"].add(value)
        if len(entry["enum"]) > MAX_ENUM_VALUES:
            entry["enum"].clear()
            entry["enum_closed"] = True


def extract_field_stats_from_docs(docs, prefix="", stats=None):
    if stats is None:
        stats = {}

    for doc in docs:
        if isinstance(doc, dict):
            for k, v in doc.items():
                path = f"{prefix}.{k}" if prefix else k
                _add_sample(stats, path, v)

                if isinstance(v, dict):
                    extract_field_stats_from_docs([v], path, stats)
                elif isinstance(v, list):
                    for item in v[:10]:
                        if isinstance(item, dict):
                            extract_field_stats_from_docs([item], path, stats)
                        else:
                            _add_sample(stats, path, item)

    return stats


def infer_field_type(path: str, types=None):
    if types:
        ordered = ["number", "date", "boolean", "objectid", "array", "object", "string"]
        return [t for t in ordered if t in types] or ["string"]

    lower = path.lower()

    if lower in {"severity", "priority", "priority_score", "score", "risk_score"}:
        return ["number"]

    if lower.endswith("_at") or lower.endswith("_time") or lower in {
        "created_at",
        "updated_at",
        "last_updated",
        "inserted_at",
        "ingested_at",
        "event_time",
        "parsed_at",
        "enriched_at",
        "timestamp",
    }:
        return ["date"]

    if lower in {"parsed", "detected", "detection", "enabled", "success"}:
        return ["boolean"]

    return ["string"]


def get_collection_schema(mongo, collection: str, context_id: str, sample_size: int = 50):
    docs = mongo.find_sorted_with_context(
        collection=collection,
        filter_query={},
        context_id=context_id,
        sort=[("_id", -1)],
        limit=sample_size,
    )

    stats = extract_field_stats_from_docs(docs)
    fields = []

    for field in sorted(stats):
        if field == "_id" or field == "context_id":
            continue

        entry = stats[field]
        item = {
            "path": field,
            "types": infer_field_type(field, entry.get("types")),
        }

        enum_values = entry.get("enum") or set()
        if enum_values and not entry.get("enum_closed"):
            item["enum"] = sorted(enum_values, key=lambda x: str(x))

        fields.append(item)

    return fields
