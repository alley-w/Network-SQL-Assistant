import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from network_sql.import_snapshot import import_snapshot
from network_sql.source import database_path
from network_sql.executor import execute_query


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'export.json'
        self.target = self.root / 'snapshot.db'
        self.payload = {
            'sites': [{'id': 1, 'name': 'Test site'}],
            'devices': [{'id': 1, 'hostname': 'test-router', 'site_id': 1, 'device_type': 'router'}],
            'device_metrics': [{'device_id': 1, 'collected_at': '2026-11-01 12:00:00', 'cpu_pct': 92, 'memory_pct': 43}],
        }

    def write(self):
        self.source.write_text(json.dumps(self.payload))

    def test_import_query_and_configured_source_without_demo_rows(self):
        self.write()
        self.assertEqual(import_snapshot(self.source, self.target)['device_metrics'], 1)
        original = self.target.read_bytes()
        with patch.dict(os.environ, {'NETWORK_DB_PATH': str(self.target)}):
            self.assertEqual(database_path(), self.target)
            self.assertEqual(execute_query(database_path(), 'SELECT hostname FROM devices')['rows'], [['test-router']])
        self.assertEqual(self.target.read_bytes(), original)
        with self.assertRaises(ValueError):
            import_snapshot(self.source, self.target)

    def test_invalid_values_never_publish_database(self):
        for value in [-1, 101, float('nan'), True]:
            self.payload['device_metrics'][0]['cpu_pct'] = value
            self.write()
            with self.subTest(value=value), self.assertRaises(ValueError):
                import_snapshot(self.source, self.target)
            self.assertFalse(self.target.exists())

    def test_bad_references_duplicates_and_timestamps_rejected(self):
        for field, value in [('device_id', 99), ('collected_at', '2026-02-30 00:00:00')]:
            old = self.payload['device_metrics'][0][field]
            self.payload['device_metrics'][0][field] = value
            self.write()
            with self.subTest(field=field), self.assertRaises(ValueError):
                import_snapshot(self.source, self.target)
            self.assertFalse(self.target.exists())
            self.payload['device_metrics'][0][field] = old
        self.payload['device_metrics'] *= 2
        self.write()
        with self.assertRaises(ValueError):
            import_snapshot(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_missing_configured_source_is_not_created(self):
        with patch.dict(os.environ, {'NETWORK_DB_PATH': str(self.target)}):
            with self.assertRaises(ValueError):
                database_path()
        self.assertFalse(self.target.exists())
