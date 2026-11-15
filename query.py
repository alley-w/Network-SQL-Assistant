"""Constrain untrusted SQL with SQLite's engine-level authorizer."""
import sqlite3
import time
from contextlib import closing
from pathlib import Path

TABLES = {"sites", "devices", "device_metrics"}
FUNCTIONS = {"count", "avg", "sum", "min", "max", "round", "abs", "coalesce",
             "nullif", "ifnull", "date", "datetime", "strftime", "julianday",
             "unixepoch", "lower", "upper", "length", "substr", "substring"}


def authorize(action, first, second, database, source):
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    # SQLite may omit the database name for COUNT(*) reads without a column.
    if action == sqlite3.SQLITE_READ and first in TABLES and (
        database == "main" or (database is None and second == "")
    ):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and (second or "").lower() in FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def execute_query(path, sql, *, max_rows=100, timeout_seconds=2.0):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 20000:
        raise ValueError("Expected SQL text between 1 and 20,000 characters.")
    if not 1 <= max_rows <= 100 or not 0 < timeout_seconds <= 2:
        raise ValueError("Query limits must be 1–100 rows and at most 2 seconds.")
    if sql.strip() == "UNSUPPORTED":
        raise ValueError("This question cannot be answered from the current schema.")
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=timeout_seconds)) as db:
        db.execute("PRAGMA query_only = ON")
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1000000)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 20000)
        db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 50)
        db.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 50)
        db.set_authorizer(authorize)
        deadline = time.monotonic() + timeout_seconds
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        try:
            # execute(), unlike executescript(), rejects multiple statements.
            cursor = db.execute(sql)
            if cursor.description is None:
                raise ValueError("Only result-producing read queries are allowed.")
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(max_rows + 1)
        except sqlite3.Error as error:
            raise ValueError(f"Query rejected or stopped: {error}") from None
        return {"columns": columns, "rows": [list(row) for row in rows[:max_rows]],
                "truncated": len(rows) > max_rows}
