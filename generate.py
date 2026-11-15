"""Generate SQL for review, or run it with --execute and enforced restrictions."""
import argparse
import json
import os
import sqlite3
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app import seed
from pathlib import Path
from query import execute_query


def build_messages(db, question):
    schema = "\n".join(row[0] + ";" for row in db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ))
    return [
        {"role": "system", "content": (
            "Translate the user's network monitoring question into SQLite SQL. "
            "Return exactly one SELECT query (WITH is allowed), without Markdown or explanation. "
            "Never modify data. Use only the schema below. If the question cannot be answered "
            "from this schema, return UNSUPPORTED. Do not invent tables or columns. "
            "Timestamps are UTC text in YYYY-MM-DD HH:MM:SS format. CPU and memory are "
            "percentages. A sample is not an incident or an outage. Use explicit date ranges; "
            "if a relative date has no reference date, return UNSUPPORTED. "
            "Use deterministic ordering for rankings, including a tie breaker. "
            "Limit lists to 100 rows unless the user requests fewer.\n\nSchema:\n" + schema
        )},
        {"role": "user", "content": question},
    ]


def generate_sql(messages):
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    model = os.environ.get("LLM_MODEL", "").strip()
    key = os.environ.get("LLM_API_KEY", "")
    if not base or not model:
        raise ValueError("Set LLM_BASE_URL and LLM_MODEL in your local .env file.")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("LLM_BASE_URL must be an HTTP(S) API base URL without credentials, query, or fragment.")
    if key and parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "host.docker.internal"}:
        raise ValueError("Use HTTPS when sending an API key to a remote provider.")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = Request(base + "/chat/completions", headers=headers,
                      data=json.dumps({"model": model, "messages": messages}).encode())
    try:
        with urlopen(request, timeout=90) as response:
            payload = json.load(response)
    except HTTPError as error:
        # Provider bodies may echo input/configuration; keep errors concise.
        raise ValueError(f"Model service returned HTTP {error.code}. Check URL, model, credentials, and quota.") from None
    except (URLError, TimeoutError):
        raise ValueError("Could not reach the model service within the timeout. Check that it is running and reachable.") from None
    try:
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError
        return content.strip()
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("Model service returned no text in the expected Chat Completions format.") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--preview", action="store_true", help="Show the prompt without contacting a model")
    parser.add_argument("--execute", action="store_true", help="Run generated SQL with restricted read-only access")
    args = parser.parse_args()
    if not args.question.strip():
        parser.error("question must not be empty")
    path = Path("data/network.db")
    seed(path)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        messages = build_messages(db, args.question)
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
