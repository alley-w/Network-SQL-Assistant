"""Generate SQL from a monitoring question."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from network_sql.source import database_path, dataset_caption
from network_sql.llm import build_messages, generate_sql
from network_sql.executor import execute_query

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--preview", action="store_true", help="Show the prompt without contacting a model")
    parser.add_argument("--execute", action="store_true", help="Run generated SQL with restricted read-only access")
    parser.add_argument("--reference-date", help="UTC reference date in YYYY-MM-DD format for today/yesterday/tomorrow")
    args = parser.parse_args()
    if not args.question.strip():
        parser.error("question must not be empty")
    path = database_path()
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            messages = build_messages(db, args.question, args.reference_date)
    except ValueError as error:
        print(f"Question needs clarification: {error}", file=sys.stderr)
        return 2
    if args.preview:
        print(json.dumps(messages, indent=2))
        return 0
    try:
        sql = generate_sql(messages)
    except (ValueError, json.JSONDecodeError) as error:
        print(f"Generation failed: {error}", file=sys.stderr)
        return 1
    print("Generated SQL:\n" if args.execute else "Model output for review only — not validated or executed:\n")
    print(sql)
    if args.execute:
        try:
            result = execute_query(path, sql)
        except ValueError as error:
            print(f"Execution failed: {error}", file=sys.stderr)
            return 1
        print("\n" + json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
