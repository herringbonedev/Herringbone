from query_parser import parse_q_string
from filters import build_range_filters
from pagination import coerce_after, apply_after
from serializer import serialize
from config import SORTABLE_FIELDS


def search_collection_service(mongo, collection, params):
    filter_query = parse_q_string(params.q)
    after_oid = coerce_after(params.after)
    filter_query = apply_after(filter_query, after_oid)

    filter_query = build_range_filters(
        collection,
        filter_query,
        params.severity_min,
        params.severity_max,
        params.from_ts,
        params.to_ts,
    )

    sort_field = params.sort or "_id"
    if sort_field not in SORTABLE_FIELDS.get(collection, set()):
        raise HTTPException(400, "Sorting by this field is not allowed")

    sort_dir = 1 if params.order == "asc" else -1

    results = mongo.find_sorted(
        collection=collection,
        filter_query=filter_query,
        sort=[(sort_field, sort_dir)],
        limit=params.limit,
    )

    results = serialize(results)

    next_after = None
    if results:
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


def get_collection_fields(mongo, collection: str, sample_size: int = 100):
    docs = mongo.find_sorted(
        collection=collection,
        filter_query={},
        sort=[("_id", -1)],
        limit=sample_size,
    )

    fields = extract_fields_from_docs(docs)
    return sorted(fields)

