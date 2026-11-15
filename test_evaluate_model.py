import tempfile
import json
import unittest
from pathlib import Path

from app import seed
from evaluate_model import evaluate_cases


class EvaluationTests(unittest.TestCase):
    def test_challenge_reference_answers(self):
        from query import execute_query
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db"
            seed(path)
            for case in json.loads(Path(__file__).with_name("challenge_cases.json").read_text()):
                if "sql" in case:
                    with self.subTest(case=case["id"]):
                        self.assertEqual(execute_query(path, case["sql"])["rows"], case["expected_rows"])

    def test_abstention_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db"
            seed(path)
            cases = [
                {"id": "missing", "question": "Downtime?", "expected_status": "unsupported"},
                {"id": "invented", "question": "Downtime?", "expected_status": "unsupported"},
                {"id": "answerable", "question": "Count devices", "expected_rows": [[6]]},
            ]
            responses = iter(["UNSUPPORTED", "SELECT 0", "UNSUPPORTED"])
            report = evaluate_cases(path, cases, lambda messages: next(responses))
            self.assertEqual([r["status"] for r in report["results"]], ["pass", "wrong_abstention", "wrong_abstention"])
            self.assertEqual(report["categories"]["unsupported"], {"total": 2, "passed": 1})

    def test_distinguishes_pass_wrong_and_execution_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db"
            seed(path)
            cases = [{"id": str(i), "question": "How many devices?", "expected_rows": [[6]]} for i in range(4)]
            responses = iter(["SELECT COUNT(*) FROM devices", "SELECT 5", "DELETE FROM devices", "SELECT * FROM device_metrics"])
            report = evaluate_cases(path, cases, lambda messages: next(responses))
            self.assertEqual([r["status"] for r in report["results"]], ["pass", "wrong_result", "execution_error", "wrong_result"])
            self.assertEqual(report["accuracy"], 0.25)
            self.assertTrue(report["results"][3]["truncated"])

    def test_generation_failure_is_recorded(self):
        def fail(messages):
            raise ValueError("Model service returned HTTP 429")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db"
            seed(path)
            report = evaluate_cases(path, [{"id": "count", "question": "Count devices", "expected_rows": [[6]]}], fail)
            self.assertEqual(report["results"][0]["status"], "generation_error")
            self.assertEqual(report["passed"], 0)


if __name__ == "__main__":
    unittest.main()
