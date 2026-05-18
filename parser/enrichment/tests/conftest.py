import importlib
import os
import sys
import types

import pytest


class DummyAuditLogger:
    def __init__(self, *args, **kwargs):
        self.records = []

    def log(self, *args, **kwargs):
        self.records.append({"args": args, "kwargs": kwargs})
        return None


def _install_missing_dependency_stubs():
    """Keep tests independent of real Mongo/audit infrastructure."""
    bson_mod = types.ModuleType("bson")

    class ObjectId(str):
        @classmethod
        def is_valid(cls, value):
            if not isinstance(value, str) or len(value) != 24:
                return False
            try:
                int(value, 16)
                return True
            except ValueError:
                return False

    bson_mod.ObjectId = ObjectId
    sys.modules.setdefault("bson", bson_mod)

    sys.modules.setdefault("modules", types.ModuleType("modules"))
    sys.modules.setdefault("modules.database", types.ModuleType("modules.database"))
    sys.modules.setdefault("modules.audit", types.ModuleType("modules.audit"))

    mongo_db_mod = types.ModuleType("modules.database.mongo_db")

    class HerringboneMongoDatabase:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    mongo_db_mod.HerringboneMongoDatabase = HerringboneMongoDatabase
    sys.modules.setdefault("modules.database.mongo_db", mongo_db_mod)

    mongo_bulk_mod = types.ModuleType("modules.database.mongo_bulk")

    class HerringboneMongoBulkOperations:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    mongo_bulk_mod.HerringboneMongoBulkOperations = HerringboneMongoBulkOperations
    sys.modules.setdefault("modules.database.mongo_bulk", mongo_bulk_mod)

    audit_mod = types.ModuleType("modules.audit.logger")
    audit_mod.AuditLogger = DummyAuditLogger
    sys.modules.setdefault("modules.audit.logger", audit_mod)


@pytest.fixture(autouse=True)
def enrichment_test_env(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_SVC", "test.service")
    monkeypatch.setenv("EXTRACTOR_BATCH_SVC", "")
    monkeypatch.setenv("CONTEXT_ID", "default")
    monkeypatch.setenv("HB_ENTERPRISE", "false")
    monkeypatch.setenv("EXTRACTOR_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_POLL_INTERVAL", "0.001")
    monkeypatch.setenv("ENRICHMENT_BATCH_SIZE", "500")
    monkeypatch.setenv("EXTRACTOR_BATCH_SIZE", "250")
    yield


@pytest.fixture()
def enrichment(monkeypatch):
    _install_missing_dependency_stubs()
    sys.modules.pop("app.enrichment", None)
    svc = importlib.import_module("app.enrichment")

    svc.audit = DummyAuditLogger()
    svc._metrics.update({"processed": 0, "matched_cards": 0, "failed": 0, "batches": 0, "last_log": 10**18})
    svc._card_cache.update({"context_id": None, "cards": [], "prepared": None, "loaded_at": 0.0})
    return svc


class FakeMongo:
    def __init__(self, cards=None):
        self.cards = cards or []

    def find_with_context(self, collection, query, *, context_id):
        if collection == "parse_cards":
            return list(self.cards)
        return []


class FakeBulk:
    def __init__(self, events=None):
        self.events = events or {}
        self.inserted = []
        self.updates = []

    def find_many_by_ids(self, collection, ids, *, context_id, id_field="_id", projection=None, preserve_order=False, include_missing_default_context=False):
        assert collection == "events"
        found = []
        for value in ids:
            key = str(value)
            if key in self.events:
                found.append(dict(self.events[key]))
        return found

    def insert_many_context(self, collection, docs, *, context_id, ordered=False):
        assert collection == "parse_results"
        for doc in docs:
            item = dict(doc)
            item["context_id"] = context_id
            self.inserted.append(item)
        return True

    def update_many_by_ids(self, collection, ids, set_fields, *, context_id, id_field="_id", include_missing_default_context=False):
        assert collection == "event_state"
        update = {
            "ids": list(ids),
            "id_field": id_field,
            "context_id": context_id,
            "set_fields": dict(set_fields),
        }
        self.updates.append(update)
        return len(update["ids"])

    def release_batch_by_ids(self, collection, ids, release_fields, *, context_id, id_field="_id", include_missing_default_context=False):
        return self.update_many_by_ids(
            collection,
            ids,
            release_fields,
            context_id=context_id,
            id_field=id_field,
            include_missing_default_context=include_missing_default_context,
        )
