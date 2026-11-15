import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import seed
from query import execute_query


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "network.db"
        seed(self.path)

    def test_reference_answers(self):
        for case in json.loads(Path(__file__).with_name("examples.json").read_text()):
            with self.subTest(case=case["id"]):
                self.assertEqual(execute_query(self.path, case["sql"])["rows"], case["expected_rows"])

    def test_blocked_operations(self):
        statements = [
            "DELETE FROM devices;", "UPDATE devices SET hostname = 'changed';",
            "INSERT INTO sites VALUES (4, 'Other');", "DROP TABLE devices;",
            "CREATE TABLE other (id);", "PRAGMA query_only = OFF;",
            "ATTACH DATABASE ':memory:' AS other;", "BEGIN;",
            "SELECT * FROM sqlite_master;", "SELECT load_extension('anything');",
            "SELECT randomblob(100000000);", "SELECT * FROM pragma_database_list;",
            "SELECT * FROM devices; DELETE FROM devices;",
            "WITH d AS (SELECT 1) DELETE FROM devices;",
        ]
        for sql in statements:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                execute_query(self.path, sql)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM devices").fetchone()[0], 6)

    def test_cte_and_semicolon_in_literal(self):
        result = execute_query(self.path, "WITH d AS (SELECT hostname FROM devices) SELECT COUNT(*) FROM d;")
        self.assertEqual(result["rows"], [[6]])
        self.assertEqual(execute_query(self.path, "SELECT ';' AS punctuation;")["rows"], [[";"]])

    def test_result_cap(self):
        result = execute_query(self.path, "SELECT * FROM device_metrics;")
        self.assertEqual(len(result["rows"]), 100)
        self.assertTrue(result["truncated"])

    def test_expensive_query_stops(self):
        with self.assertRaisesRegex(ValueError, "interrupted"):
            execute_query(self.path, "SELECT COUNT(*) FROM device_metrics a CROSS JOIN device_metrics b CROSS JOIN device_metrics c;", timeout_seconds=0.001)

    def test_invalid_and_unsupported(self):
        for sql in ["", "UNSUPPORTED", "SELECT unknown FROM devices", "x" * 20001]:
            with self.subTest(sql=sql[:30]), self.assertRaises(ValueError):
                execute_query(self.path, sql)


if __name__ == "__main__":
    unittest.main()
