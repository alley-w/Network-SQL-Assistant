import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from network_sql.database import seed
from network_sql.dates import ClarificationRequired, resolve_question
from network_sql.evaluate_model import evaluate_cases


class DateContextTests(unittest.TestCase):
    def test_missing_reference(self):
        for day in ["today", "Yesterday", "TOMORROW"]:
            with self.subTest(day=day), self.assertRaises(ClarificationRequired):
                resolve_question(f"CPU {day}?")

    def test_boundaries(self):
        self.assertEqual(resolve_question("CPU yesterday?", "2026-01-01"), "CPU on 2025-12-31 UTC?")
        self.assertEqual(resolve_question("CPU tomorrow?", "2024-02-28"), "CPU on 2024-02-29 UTC?")
        self.assertEqual(resolve_question("CPU today?", "2026-11-04"), "CPU on 2026-11-04 UTC?")

    def test_invalid_dates(self):
        for value in ["2026-02-30", "20261104", "2026-1-4", "bad"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_question("CPU today", value)

    def test_other_relative_periods_need_explicit_range(self):
        for phrase in ["last week", "past 7 days", "3 days ago", "recently", "now"]:
            with self.subTest(phrase=phrase), self.assertRaises(ClarificationRequired):
                resolve_question(f"CPU {phrase}", "2026-11-04")

    def test_explicit_date_unchanged(self):
        self.assertEqual(resolve_question("CPU on November 3, 2026"), "CPU on November 3, 2026")

    def test_clarification_skips_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db"
            seed(path)
            model = Mock(side_effect=AssertionError("Must not call model"))
            report = evaluate_cases(path, [{"id": "relative", "question": "CPU yesterday?", "expected_status": "unsupported"}], model)
            model.assert_not_called()
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["results"][0]["decision_source"], "application")


if __name__ == "__main__":
    unittest.main()
