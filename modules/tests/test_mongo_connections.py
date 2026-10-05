"""Connection lifecycle regressions; no running MongoDB is required."""

import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import errors
from modules.database import mongo_bulk, mongo_db


class MongoConnectionTests(unittest.TestCase):
    def wrappers(self):
        return (
            (mongo_db, mongo_db.HerringboneMongoDatabase),
            (mongo_bulk, mongo_bulk.HerringboneMongoBulkOperations),
        )

    def test_repeated_crud_reuses_client_and_pool(self):
        client = MagicMock()
        database = client.__getitem__.return_value
        database.__getitem__.return_value.find_one.side_effect = lambda q, p: dict(q)
        with patch.object(mongo_db, "MongoClient", return_value=client) as factory:
            wrapper = mongo_db.HerringboneMongoDatabase(host="mongodb", database="herringbone")
            for index in range(100):
                self.assertEqual(wrapper.find_one("events", {"_id": index}), {"_id": index})
            factory.assert_called_once()
            client.admin.command.assert_called_once_with("ping")
            client.close.assert_not_called()

    def test_concurrent_first_use_creates_one_client(self):
        for module, wrapper_type in self.wrappers():
            with self.subTest(wrapper=wrapper_type.__name__):
                barrier = Barrier(16)
                client = MagicMock()
                client.admin.command.side_effect = lambda command: time.sleep(0.01)
                with patch.object(module, "MongoClient", return_value=client) as factory:
                    wrapper = wrapper_type(host="mongodb", database="herringbone")

                    def open_connection(_):
                        barrier.wait(timeout=5)
                        return wrapper.open_mongo_connection()

                    with ThreadPoolExecutor(max_workers=16) as pool:
                        results = list(pool.map(open_connection, range(16)))
                    factory.assert_called_once()
                    client.admin.command.assert_called_once_with("ping")
                    for result in results:
                        self.assertIs(result[0], client)
                        self.assertIs(result[1], client.__getitem__.return_value)

    def test_failed_ping_is_closed_and_next_call_can_reconnect(self):
        for module, wrapper_type in self.wrappers():
            for error_type, message in (
                (errors.ServerSelectionTimeoutError, "server unreachable"),
                (errors.OperationFailure, "authentication failed"),
                (errors.AutoReconnect, "connection lost"),
            ):
                with self.subTest(wrapper=wrapper_type.__name__, error=error_type.__name__):
                    failed, healthy = MagicMock(), MagicMock()
                    failed.admin.command.side_effect = error_type("connection lost")
                    with patch.object(module, "MongoClient", side_effect=[failed, healthy]) as factory:
                        wrapper = wrapper_type(host="mongodb", database="herringbone")
                        expected = RuntimeError if error_type is not errors.AutoReconnect else error_type
                        with self.assertRaisesRegex(expected, message):
                            wrapper.open_mongo_connection()
                        failed.close.assert_called_once()
                        self.assertIsNone(wrapper.client)
                        self.assertIsNone(wrapper.db)
                        self.assertIs(wrapper.open_mongo_connection()[0], healthy)
                        self.assertEqual(factory.call_count, 2)
                        healthy.admin.command.assert_called_once_with("ping")

    def test_close_is_idempotent_and_reopen_creates_a_new_client(self):
        for module, wrapper_type in self.wrappers():
            with self.subTest(wrapper=wrapper_type.__name__):
                first, second = MagicMock(), MagicMock()
                with patch.object(module, "MongoClient", side_effect=[first, second]) as factory:
                    wrapper = wrapper_type(host="mongodb", database="herringbone")
                    wrapper.open_mongo_connection()
                    wrapper.close_mongo_connection()
                    wrapper.close_mongo_connection()
                    first.close.assert_called_once()
                    self.assertIsNone(wrapper.client)
                    self.assertIsNone(wrapper.db)
                    self.assertIs(wrapper.open_mongo_connection()[0], second)
                    self.assertEqual(factory.call_count, 2)

    def test_operation_failure_does_not_replace_existing_client(self):
        client = MagicMock()
        collection = client.__getitem__.return_value.__getitem__.return_value
        collection.find_one.side_effect = [errors.AutoReconnect("lost connection"), {"_id": 1}]
        with patch.object(mongo_db, "MongoClient", return_value=client) as factory:
            wrapper = mongo_db.HerringboneMongoDatabase(host="mongodb", database="herringbone")
            with self.assertRaisesRegex(RuntimeError, "MongoDB operation failed"):
                wrapper.find_one("events", {"_id": 1})
            self.assertEqual(wrapper.find_one("events", {"_id": 1}), {"_id": 1})
            factory.assert_called_once()
            client.close.assert_not_called()

    def test_bulk_retains_pool_options_and_context_manager_cleanup(self):
        client = MagicMock()
        with patch.object(mongo_bulk, "MongoClient", return_value=client) as factory:
            wrapper = mongo_bulk.HerringboneMongoBulkOperations(
                host="mongodb", max_pool_size=7, retry_writes=False,
                server_selection_timeout_ms=123,
            )
            with self.assertRaisesRegex(ValueError, "body failed"):
                with wrapper:
                    self.assertIs(wrapper.raw_db, client.__getitem__.return_value)
                    raise ValueError("body failed")
            factory.assert_called_once_with(
                wrapper.uri, serverSelectionTimeoutMS=123, retryWrites=False, maxPoolSize=7,
            )
            client.close.assert_called_once()
            self.assertIsNone(wrapper.client)
            self.assertIsNone(wrapper.db)


if __name__ == "__main__":
    unittest.main()
