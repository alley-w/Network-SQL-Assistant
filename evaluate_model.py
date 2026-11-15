"""Measure generated SQL results against our small reference set."""
import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app import seed
from generate import build_messages, generate_sql
from query import execute_query
from date_context import ClarificationRequired


def evaluate_cases(path, cases, generate=generate_sql):
    results = []
    for case in cases:
        started = time.monotonic()
        unsupported = case.get("expected_status") == "unsupported"
        result = {"id": case["id"], "question": case["question"],
                  "expected_status": "unsupported" if unsupported else "rows"}
        if not unsupported:
            result["expected_rows"] = case["expected_rows"]
        try:
            with closing(sqlite3.connect(path)) as db:
                messages = build_messages(db, case["question"], case.get("reference_date"))
        except ClarificationRequired as error:
            result.update(status="pass" if unsupported else "wrong_abstention",
                          decision_source="application", clarification=str(error),
                          latency_seconds=round(time.monotonic() - started, 3))
            results.append(result)
            print(f"{result['status'].upper()} {case['id']} (application clarification)", flush=True)
            continue
        result["decision_source"] = "model"
        result["prompt_sha256"] = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
        try:
            sql = generate(messages)
            result["generated_sql"] = sql
        except ValueError as error:
            result.update(status="generation_error", error=str(error))
        else:
            if unsupported or sql.strip() == "UNSUPPORTED":
                result["status"] = "pass" if unsupported and sql.strip() == "UNSUPPORTED" else "wrong_abstention"
                result["latency_seconds"] = round(time.monotonic() - started, 3)
                results.append(result)
                print(f"{result['status'].upper()} {case['id']} ({result['latency_seconds']}s)", flush=True)
                continue
            try:
                actual = execute_query(path, sql)
                result["actual_rows"] = actual["rows"]
                result["truncated"] = actual["truncated"]
                result["status"] = "pass" if not actual["truncated"] and actual["rows"] == case["expected_rows"] else "wrong_result"
            except ValueError as error:
                result.update(status="execution_error", error=str(error))
        result["latency_seconds"] = round(time.monotonic() - started, 3)
        results.append(result)
        print(f"{result['status'].upper()} {case['id']} ({result['latency_seconds']}s)", flush=True)
    passed = sum(result["status"] == "pass" for result in results)
    categories = {}
    for expected in ("rows", "unsupported"):
        group = [r for r in results if r["expected_status"] == expected]
        categories[expected] = {"total": len(group), "passed": sum(r["status"] == "pass" for r in group)}
    return {"total": len(results), "passed": passed, "categories": categories,
            "accuracy": passed / len(results) if results else 0, "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="data/model-evaluation.json")
    parser.add_argument("--cases", default=str(Path(__file__).with_name("examples.json")))
    args = parser.parse_args()
    cases_file = Path(args.cases)
    cases = json.loads(cases_file.read_text())
    if not cases:
        parser.error("Reference set is empty")
    if not all(os.environ.get(key, "").strip() for key in ("LLM_BASE_URL", "LLM_MODEL")):
        parser.error("Configure LLM_BASE_URL and LLM_MODEL in .env first")
    print(f"Evaluating {len(cases)} questions; at most one model request per question.", flush=True)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "evaluation.db"
        seed(path)
        report = evaluate_cases(path, cases)
    report.update(created_at=datetime.now(timezone.utc).isoformat(),
                  model=os.environ["LLM_MODEL"],
                  dataset_sha256=hashlib.sha256(cases_file.read_bytes()).hexdigest(),
                  cases_file=cases_file.name,
                  scope="Small synthetic-data evaluation; inspect cases and prior prompt tuning before interpreting generalization.")
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\n{report['passed']}/{report['total']} correct ({report['accuracy']:.0%}). Report: {destination}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
