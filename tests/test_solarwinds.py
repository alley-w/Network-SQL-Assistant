import json
import tempfile
import unittest
from pathlib import Path

from network_sql.adapters.solarwinds import import_orion, normalize, utc_timestamp
from network_sql.executor import execute_query

FIXTURES = Path(__file__).resolve().parents[1] / 'network_sql' / 'fixtures'


class OrionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.nodes = json.loads((FIXTURES / 'orion_nodes_simulated.json').read_text())
        self.history = json.loads((FIXTURES / 'orion_history_simulated.json').read_text())

    def test_offline_import_answers_known_question(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'orion.db'
            counts = import_orion(FIXTURES / 'orion_nodes_simulated.json', FIXTURES / 'orion_history_simulated.json', db)
            self.assertEqual(counts, {'sites': 2, 'devices': 3, 'device_metrics': 6})
            result = execute_query(db, 'SELECT d.hostname, COUNT(*) FROM devices d JOIN device_metrics m ON d.id=m.device_id WHERE m.cpu_pct>80 GROUP BY d.hostname ORDER BY d.hostname')
            self.assertEqual(result['rows'], [['demo-east-router', 1], ['demo-west-router', 2]])
            with self.assertRaises(ValueError):
                import_orion(FIXTURES / 'orion_nodes_simulated.json', FIXTURES / 'orion_history_simulated.json', db)

    def test_explicit_timezone_conversion_and_ambiguous_times(self):
        self.assertEqual(utc_timestamp('2026-11-01T04:00:00-08:00'), '2026-11-01 12:00:00')
        for value in ['2026-11-01T12:00:00', 'bad', None, '2026-11-01T12:00:00.123Z']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                utc_timestamp(value)

    def test_missing_fields_fail_without_inventing_values(self):
        for key in ['NodeID', 'Caption', 'Site', 'DeviceType']:
            node = dict(self.nodes['results'][0])
            del node[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                normalize({'results': [node]}, self.history)
        self.history['results'][0]['AvgPercentMemoryUsed'] = None
        with self.assertRaises(ValueError):
            normalize(self.nodes, self.history)

    def test_bad_metric_and_unknown_node_do_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nodes = root / 'nodes.json'
            nodes.write_text(json.dumps(self.nodes))
            history = root / 'history.json'
            for key, value in [('AvgLoad', -2), ('NodeID', 999)]:
                record = dict(self.history['results'][0])
                record[key] = value
                history.write_text(json.dumps({'results': [record]}))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    import_orion(nodes, history, root / 'out.db')
                self.assertFalse((root / 'out.db').exists())
