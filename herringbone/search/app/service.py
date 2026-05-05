from fastapi import HTTPException

from app.query_parser import parse_q_string
from app.filters import build_range_filters
from app.pagination import coerce_after, apply_after
from app.serializer import serialize
from app.config import SORTABLE_FIELDS


def search_collection_service(mongo, collection, params, context_id: str):
    filter_query = parse_q_string(params.q)

    after_oid = coerce_after(params.after)
    filter_query = apply_after(filter_query, after_oid)

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

    sort_field = params.sort or "_id"
    if sort_field not in SORTABLE_FIELDS.get(collection, set()):
        raise HTTPException(400, "Sorting by this field is not allowed")

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


def extract_fields_from_docs(docs, prefix="", out=None):
    if out is None:
        out = set()

    for doc in docs:
        if isinstance(doc, dict):
            for k, v in doc.items():
                path = f"{prefix}.{k}" if prefix else k
                out.add(path)

                if isinstance(v, dict):
                    extract_fields_from_docs([v], path, out)
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    extract_fields_from_docs(v, path, out)

    return out


def infer_field_type(path: str):
    lower = path.lower()

    if lower in {"severity", "priority_score", "score", "risk_score"}:
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

    fields = sorted(extract_fields_from_docs(docs))

    return [
        {
            "path": field,
            "types": infer_field_type(field),
        }
        for field in fields
        if field != "_id"
    ]