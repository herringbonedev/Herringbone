from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4
from typing import Any, Iterable, Mapping, Sequence

from pymongo import MongoClient, errors
from pymongo.database import Database

from .mongo_db import HerringboneMongoDatabase


class HerringboneMongoBulkOperations:

    def __init__(
        self,
        *,
        user: str = "",
        password: str = "",
        database: str = "herringbone",
        host: str = "localhost",
        port: int = 27017,
        auth_source: str = "admin",
        replica_set: str | None = None,
        server_selection_timeout_ms: int = 5000,
        retry_writes: bool = True,
        max_pool_size: int = 100,

    ):
        
        self._base = HerringboneMongoDatabase(
            user=user,
            password=password,
            database=database,
            host=host,
            port=port,
            auth_source=auth_source,
            replica_set=replica_set,
        )
        self.uri = self._base.uri
        self.database = database
        self.server_selection_timeout_ms = server_selection_timeout_ms
        self.retry_writes = retry_writes
        self.max_pool_size = max_pool_size
        self.client: MongoClient | None = None
        self.db: Database | None = None
        self.last_claim_stats: dict[str, Any] = {}

        print("BULK MONGO DB")

    # ===========================
    # Connection Management
    # ===========================

    def open_mongo_connection(self) -> tuple[MongoClient, Database]:
        try:
            if self.client is None:
                self.client = MongoClient(
                    self.uri,
                    serverSelectionTimeoutMS=self.server_selection_timeout_ms,
                    retryWrites=self.retry_writes,
                    maxPoolSize=self.max_pool_size,
                )
                self.client.admin.command("ping")
                self.db = self.client[self.database]

            if self.db is None:
                self.db = self.client[self.database]

            return self.client, self.db

        except errors.ServerSelectionTimeoutError as e:
            raise RuntimeError(f"MongoDB server unreachable: {e}") from e
        except errors.OperationFailure as e:
            raise RuntimeError(f"MongoDB authentication failed: {e}") from e

    def close_mongo_connection(self):
        if self.client:
            try:
                self.client.close()
            finally:
                self.client = None
                self.db = None

    def __enter__(self) -> "HerringboneMongoBulkOperations":
        self.open_mongo_connection()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close_mongo_connection()

    @property
    def raw_db(self) -> Database:
        _, db = self.open_mongo_connection()
        return db

    # ===========================
    # Context Safety Helpers
    # ===========================

    @staticmethod
    def _require_context(context_id: str):
        if not context_id:
            raise RuntimeError("context_id is required")

    @staticmethod
    def _as_list(values: Iterable[Any] | Sequence[Any]) -> list[Any]:
        if values is None:
            return []
        if isinstance(values, list):
            return values
        return list(values)

    @staticmethod
    def _utcnow():
        return datetime.now(UTC)

    def _context_clause(
        self,
        context_id: str,
        *,
        include_missing_default_context: bool = False,
    ) -> dict:
        self._require_context(context_id)

        if include_missing_default_context and context_id == "default":
            return {
                "$or": [
                    {"context_id": context_id},
                    {"context_id": {"$exists": False}},
                    {"context_id": None},
                    {"context_id": ""},
                ]
            }

        return {"context_id": context_id}

    def _scoped_filter(
        self,
        filter_query: Mapping[str, Any] | None,
        *,
        context_id: str,
        include_missing_default_context: bool = False,
    ) -> dict:
        return {
            "$and": [
                self._context_clause(
                    context_id,
                    include_missing_default_context=include_missing_default_context,
                ),
                dict(filter_query or {}),
            ]
        }

    def _sanitize_doc(self, doc: Mapping[str, Any], *, clean_codec: bool = False) -> dict:
        payload = dict(doc)
        if clean_codec:
            payload = self._base._sanitize_payload(payload)  # reuse existing behavior
        return payload

    # ===========================
    # Generic Context-Safe Bulk APIs
    # ===========================

    def find_many_by_ids(
        self,
        collection: str,
        ids: Iterable[Any],
        *,
        context_id: str,
        id_field: str = "_id",
        projection: dict | None = None,
        preserve_order: bool = False,
        include_missing_default_context: bool = False,
    ) -> list[dict]:
        """Find documents by id_field, always scoped to one context_id."""
        id_list = self._as_list(ids)
        if not id_list:
            return []

        db = self.raw_db
        query = self._scoped_filter(
            {id_field: {"$in": id_list}},
            context_id=context_id,
            include_missing_default_context=include_missing_default_context,
        )
        docs = list(db[collection].find(query, projection or None))

        if not preserve_order:
            return docs

        by_key = {str(doc.get(id_field)): doc for doc in docs}
        return [by_key[str(value)] for value in id_list if str(value) in by_key]

    def insert_many_context(
        self,
        collection: str,
        docs: Iterable[Mapping[str, Any]],
        *,
        context_id: str,
        ordered: bool = False,
        clean_codec: bool = False,
    ):
        """Insert many documents and force the supplied context_id onto every document."""
        self._require_context(context_id)
        payload = []
        for doc in docs:
            item = self._sanitize_doc(doc, clean_codec=clean_codec)
            item["context_id"] = context_id
            payload.append(item)

        if not payload:
            return None

        db = self.raw_db
        return db[collection].insert_many(payload, ordered=ordered)

    def update_many_by_ids(
        self,
        collection: str,
        ids: Iterable[Any],
        set_fields: Mapping[str, Any],
        *,
        context_id: str,
        id_field: str = "_id",
        unset_fields: Mapping[str, Any] | None = None,
        include_missing_default_context: bool = False,
    ) -> int:
        """Update many documents by id_field, always scoped to one context_id."""
        id_list = self._as_list(ids)
        if not id_list:
            return 0

        update_doc: dict[str, Any] = {"$set": dict(set_fields or {})}
        update_doc["$set"]["context_id"] = context_id

        if unset_fields:
            update_doc["$unset"] = dict(unset_fields)

        db = self.raw_db
        query = self._scoped_filter(
            {id_field: {"$in": id_list}},
            context_id=context_id,
            include_missing_default_context=include_missing_default_context,
        )
        res = db[collection].update_many(query, update_doc)
        return getattr(res, "modified_count", 0)

    def update_many_context(
        self,
        collection: str,
        filter_query: Mapping[str, Any],
        set_fields: Mapping[str, Any],
        *,
        context_id: str,
        unset_fields: Mapping[str, Any] | None = None,
        include_missing_default_context: bool = False,
    ) -> int:
        """Update many documents matching a filter, always scoped to one context_id."""
        update_doc: dict[str, Any] = {"$set": dict(set_fields or {})}
        update_doc["$set"]["context_id"] = context_id

        if unset_fields:
            update_doc["$unset"] = dict(unset_fields)

        db = self.raw_db
        query = self._scoped_filter(
            filter_query,
            context_id=context_id,
            include_missing_default_context=include_missing_default_context,
        )
        res = db[collection].update_many(query, update_doc)
        return getattr(res, "modified_count", 0)

    def claim_batch(
        self,
        collection: str,
        filter_query: Mapping[str, Any],
        claim_fields: Mapping[str, Any],
        *,
        context_id: str,
        limit: int,
        sort: list[tuple[str, int]] | None = None,
        projection: dict | None = None,
        claimable_filter: Mapping[str, Any] | None = None,
        claimed_by_field: str = "claimed_by",
        include_missing_default_context: bool = False,
    ) -> list[dict]:
        """
        Claim a context-local batch of documents.

        This is generic and can be reused by parser, detector, correlator, or any
        batch worker. The result set is guaranteed to be scoped to one context_id.

        Each claim attempt gets a unique claim_token. Readback uses that token,
        so this call only returns documents claimed by this exact batch, not older
        documents with the same claimed_by value.
        """
        self._require_context(context_id)
        limit = max(1, int(limit or 1))
        sort = sort or [("created_at", 1), ("_id", 1)]

        claim_fields = dict(claim_fields or {})
        claim_fields["context_id"] = context_id

        claim_token = claim_fields.get("claim_token") or claim_fields.get("claimed_token")
        if not claim_token:
            claim_token = str(uuid4())
            claim_fields["claim_token"] = claim_token

        if claimable_filter is None:
            claimable_filter = {
                "$or": [
                    {"claimed": False},
                    {"claimed": {"$exists": False}},
                    {"lease_expires_at": {"$lt": self._utcnow()}},
                ]
            }

        db = self.raw_db

        candidate_query = self._scoped_filter(
            {
                "$and": [
                    dict(filter_query or {}),
                    dict(claimable_filter or {}),
                ]
            },
            context_id=context_id,
            include_missing_default_context=include_missing_default_context,
        )

        candidate_projection = {"_id": 1}
        if projection:
            candidate_projection.update(projection)

        candidates = list(
            db[collection]
            .find(candidate_query, candidate_projection)
            .sort(sort)
            .limit(limit)
        )

        if not candidates:
            self.last_claim_stats = {
                "collection": collection,
                "context_id": context_id,
                "requested_limit": limit,
                "candidate_count": 0,
                "matched_count": 0,
                "modified_count": 0,
                "claimed_count": 0,
                "claim_token": claim_token,
            }
            return []

        candidate_ids = [doc["_id"] for doc in candidates]

        claim_query = self._scoped_filter(
            {
                "$and": [
                    {"_id": {"$in": candidate_ids}},
                    dict(filter_query or {}),
                    dict(claimable_filter or {}),
                ]
            },
            context_id=context_id,
            include_missing_default_context=include_missing_default_context,
        )

        claim_result = db[collection].update_many(claim_query, {"$set": claim_fields})

        readback_filter: dict[str, Any] = {
            "_id": {"$in": candidate_ids},
            "claim_token": claim_token,
        }

        if claimed_by_field and claimed_by_field in claim_fields:
            readback_filter[claimed_by_field] = claim_fields[claimed_by_field]

        readback_query = self._scoped_filter(
            readback_filter,
            context_id=context_id,
            include_missing_default_context=include_missing_default_context,
        )

        claimed_docs = list(db[collection].find(readback_query).sort(sort))

        self.last_claim_stats = {
            "collection": collection,
            "context_id": context_id,
            "requested_limit": limit,
            "candidate_count": len(candidates),
            "matched_count": getattr(claim_result, "matched_count", 0),
            "modified_count": getattr(claim_result, "modified_count", 0),
            "claimed_count": len(claimed_docs),
            "claim_token": claim_token,
        }

        return claimed_docs

    def release_batch_by_ids(
        self,
        collection: str,
        ids: Iterable[Any],
        release_fields: Mapping[str, Any],
        *,
        context_id: str,
        id_field: str = "_id",
        include_missing_default_context: bool = False,
    ) -> int:
        """Release/clear a claimed batch by id_field, always scoped to one context_id."""
        return self.update_many_by_ids(
            collection,
            ids,
            release_fields,
            context_id=context_id,
            id_field=id_field,
            include_missing_default_context=include_missing_default_context,
        )

    def count_context(
        self,
        collection: str,
        filter_query: Mapping[str, Any] | None = None,
        *,
        context_id: str,
        include_missing_default_context: bool = False,
    ) -> int:
        """Count documents matching a filter, always scoped to one context_id."""
        db = self.raw_db
        query = self._scoped_filter(
            filter_query or {},
            context_id=context_id,
            include_missing_default_context=include_missing_default_context,
        )
        return db[collection].count_documents(query)

    def find_next_context_with_work(
        self,
        collection: str,
        filter_query: Mapping[str, Any],
        *,
        context_field: str = "context_id",
        oldest_field: str = "created_at",
        claimable_filter: Mapping[str, Any] | None = None,
        exclude_empty_context: bool = True,
    ) -> dict | None:
        """
        Discover the next context with pending work without returning tenant data.

        This is intended for schedulers. After it returns a context_id, the worker
        must call claim_batch(..., context_id=that_context_id, ...).
        """
        if claimable_filter is None:
            claimable_filter = {
                "$or": [
                    {"claimed": False},
                    {"claimed": {"$exists": False}},
                    {"lease_expires_at": {"$lt": self._utcnow()}},
                ]
            }

        match_filter: dict[str, Any] = {
            "$and": [
                dict(filter_query or {}),
                dict(claimable_filter or {}),
            ]
        }

        if exclude_empty_context:
            match_filter["$and"].append({context_field: {"$exists": True, "$nin": [None, ""]}})

        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": f"${context_field}",
                    "oldest": {"$min": f"${oldest_field}"},
                    "pending": {"$sum": 1},
                }
            },
            {"$sort": {"oldest": 1}},
            {"$limit": 1},
        ]

        db = self.raw_db
        rows = list(db[collection].aggregate(pipeline))
        if not rows:
            return None

        row = rows[0]
        return {
            "context_id": row.get("_id"),
            "oldest": row.get("oldest"),
            "pending": row.get("pending", 0),
        }