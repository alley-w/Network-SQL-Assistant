import tempfile
import unittest
from pathlib import Path

from app import seed
from evaluate_model import evaluate_cases


class EvaluationTests(unittest.TestCase):
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
