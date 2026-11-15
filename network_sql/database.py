"""Schema and reproducible synthetic network data."""
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def seed(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY, hostname TEXT NOT NULL UNIQUE,
                site_id INTEGER NOT NULL REFERENCES sites(id),
                device_type TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS device_metrics (
                device_id INTEGER NOT NULL REFERENCES devices(id),
                collected_at TEXT NOT NULL,
                cpu_pct REAL NOT NULL CHECK(cpu_pct BETWEEN 0 AND 100),
                memory_pct REAL NOT NULL CHECK(memory_pct BETWEEN 0 AND 100),
                PRIMARY KEY (device_id, collected_at));
        """)
        if db.execute("SELECT COUNT(*) FROM sites").fetchone()[0]:
            return
        db.executemany("INSERT INTO sites VALUES (?, ?)",
                       [(1, "Vancouver"), (2, "Toronto"), (3, "Montreal")])
        devices = [(i, f"site-{(i-1)//2+1}-{kind}-01", (i-1)//2+1, kind)
                   for i, kind in enumerate(["router", "switch"] * 3, start=1)]
        db.executemany("INSERT INTO devices VALUES (?, ?, ?, ?)", devices)
        rng = random.Random(42)
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        rows = []
        for hour in range(7 * 24):
            timestamp = (start + timedelta(hours=hour)).strftime("%Y-%m-%d %H:%M:%S")
            for device_id, *_ in devices:
                # Device 3 has repeated CPU spikes during the working day.
                cpu = rng.uniform(82, 98) if device_id == 3 and 9 <= hour % 24 < 17 else rng.uniform(10, 65)
                rows.append((device_id, timestamp, round(cpu, 2), round(rng.uniform(25, 85), 2)))
        db.executemany("INSERT INTO device_metrics VALUES (?, ?, ?, ?)", rows)

