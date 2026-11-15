"""Choose the demo database or an explicitly configured local snapshot."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from network_sql.database import seed

COLUMNS = {
    'sites': {'id', 'name'},
    'devices': {'id', 'hostname', 'site_id', 'device_type'},
    'device_metrics': {'device_id', 'collected_at', 'cpu_pct', 'memory_pct'},
}


def validate_schema(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        for table, columns in COLUMNS.items():
            kind = db.execute('SELECT type FROM sqlite_master WHERE name=?', (table,)).fetchone()
            actual = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
            if kind != ('table',) or actual != columns:
                raise ValueError(f'Snapshot table {table} must have exactly these columns: {", ".join(sorted(columns))}')


def database_path():
    configured = os.environ.get('NETWORK_DB_PATH', '').strip()
    path = Path(configured or 'data/network.db')
    if configured:
        if not path.is_file():
            raise ValueError('NETWORK_DB_PATH does not point to an existing snapshot. Import one first.')
        validate_schema(path)
    else:
        seed(path)
    return path


def dataset_caption():
    return ('Imported snapshot · All timestamps are UTC' if os.environ.get('NETWORK_DB_PATH', '').strip()
            else 'Synthetic dataset · November 1–7, 2026 · All dates and timestamps are UTC')
