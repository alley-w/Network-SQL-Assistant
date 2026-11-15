"""Dataset provenance and metric meaning, separate from queryable data."""
import sqlite3

METRIC_NOTES = {
    'interval_average': 'CPU and memory values are interval averages, not instantaneous readings or maxima. Interval durations are unavailable. Do not infer true instantaneous peaks, outage durations, or time-weighted averages from these rows.',
    'unknown': 'Metric aggregation and interval durations are unspecified. Report recorded values only; do not infer instantaneous peaks, durations, or time-weighted averages.',
}


def read_metadata(db):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='snapshot_metadata'").fetchone()
    if not exists:
        return {'source': 'legacy', 'simulated': False, 'metric_kind': 'unknown'}
    try:
        row = db.execute('SELECT source, simulated, metric_kind FROM snapshot_metadata').fetchone()
    except sqlite3.Error:
        return {'source': 'legacy', 'simulated': False, 'metric_kind': 'unknown'}
    if row is None or row[0] not in {'normalized_export', 'solarwinds_orion'} or row[1] not in (0, 1) or row[2] not in METRIC_NOTES:
        return {'source': 'legacy', 'simulated': False, 'metric_kind': 'unknown'}
    return {'source': row[0], 'simulated': bool(row[1]), 'metric_kind': row[2]}
