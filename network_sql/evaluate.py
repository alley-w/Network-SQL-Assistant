"""Verify our reference SQL against a fresh, reproducible database."""
import json
import sqlite3
import tempfile
from pathlib import Path

from network_sql.database import seed


def check_examples(db, examples):
    failures = 0
    for example in examples:
        try:
            actual = [list(row) for row in db.execute(example["sql"]).fetchall()]
            passed = actual == example["expected_rows"]
            print(f"{'PASS' if passed else 'FAIL'} {example['id']}: {example['question']}")
            if not passed:
                print(f"  Expected: {example['expected_rows']!r}\n  Actual:   {actual!r}")
        except sqlite3.Error as error:
            passed = False
            print(f"FAIL {example['id']}: {error}")
        failures += not passed
    print(f"\n{len(examples) - failures}/{len(examples)} reference queries passed.")
    return failures


def main():
    examples = json.loads((Path(__file__).parent / "fixtures" / "examples.json").read_text())
    if not examples:
        raise ValueError("The reference set must not be empty")
    # Never seed or change the learner's existing database volume.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "evaluation.db"
        seed(path)
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            failures = check_examples(db, examples)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
