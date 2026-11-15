"""Import a normalized JSON export into a new local SQLite snapshot."""
import argparse
import json
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from network_sql.database import seed
from network_sql.source import COLUMNS


def import_snapshot(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('Destination already exists. Choose a new snapshot filename.')
    if source.stat().st_size > 20_000_000:
        raise ValueError('Snapshot JSON must be at most 20 MB.')
    payload = json.loads(source.read_text())
    if not isinstance(payload, dict) or set(payload) != set(COLUMNS):
        raise ValueError('Export must contain sites, devices, and device_metrics arrays.')
    for table, columns in COLUMNS.items():
        rows = payload[table]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f'{table} must be a nonempty array.')
        for row in rows:
            if not isinstance(row, dict) or set(row) != columns:
                raise ValueError(f'Unexpected fields in {table}; use the documented export format.')
            for key, value in row.items():
                if key in {'id', 'site_id', 'device_id'}:
                    if type(value) is not int or value <= 0:
                        raise ValueError(f'{table}.{key} must be a positive integer.')
                elif key in {'cpu_pct', 'memory_pct'}:
                    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                        raise ValueError(f'{table}.{key} must be a percentage between 0 and 100.')
                elif not isinstance(value, str) or not value.strip() or len(value) > 200:
                    raise ValueError(f'{table}.{key} must be nonempty text of at most 200 characters.')
            if table == 'device_metrics':
                stamp = row['collected_at']
                try:
                    if datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S') != stamp:
                        raise ValueError
                except ValueError:
                    raise ValueError('collected_at must be an explicit UTC timestamp: YYYY-MM-DD HH:MM:SS.') from None
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Build privately, then publish without overwriting an existing database.
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        temporary = Path(directory) / 'snapshot.db'
        seed(temporary)
        try:
            with closing(sqlite3.connect(temporary)) as db, db:
                db.execute('PRAGMA foreign_keys=ON')
                for table in ('device_metrics', 'devices', 'sites'):
                    db.execute(f'DELETE FROM {table}')
                for table in ('sites', 'devices', 'device_metrics'):
                    columns = sorted(COLUMNS[table])
                    db.executemany(f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})',
                                   [[row[column] for column in columns] for row in payload[table]])
        except sqlite3.IntegrityError:
            raise ValueError('Export contains duplicate identifiers, duplicate samples, or invalid device/site references.') from None
        os.link(temporary, destination)
    return {table: len(rows) for table, rows in payload.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='Normalized JSON file, with UTC timestamps')
    parser.add_argument('destination', help='New SQLite database filename')
    args = parser.parse_args()
    try:
        counts = import_snapshot(args.source, args.destination)
    except (OSError, ValueError) as error:
        parser.exit(2, f'Import failed: {error}\n')
    print(f'Imported snapshot: {args.destination}')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
