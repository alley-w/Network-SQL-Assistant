"""Offline Orion export adapter; no network access or credentials required."""
import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from network_sql.import_snapshot import import_snapshot


def results(response, label):
    if not isinstance(response, dict) or not isinstance(response.get('results'), list) or not response['results']:
        raise ValueError(f'{label} must contain a nonempty results array.')
    if not all(isinstance(row, dict) for row in response['results']):
        raise ValueError(f'{label} results must be objects.')
    return response['results']


def required(row, key):
    if key not in row or row[key] is None:
        raise ValueError(f'Missing Orion field: {key}. No default value was substituted.')
    return row[key]


def utc_timestamp(value):
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.microsecond:
            raise ValueError
        return parsed.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OverflowError):
        raise ValueError('Orion DateTime must be ISO 8601 with a timezone and whole-second precision; normalize the export explicitly.') from None


def normalize(nodes_response, history_response):
    """Map complete query responses; Site/DeviceType are deployment-defined aliases.

    History must be a single consistent aggregation tier. AvgLoad and
    AvgPercentMemoryUsed retain their average semantics, not instantaneous peaks.
    The shared importer performs type, range, uniqueness, and reference checks.
    """
    nodes = results(nodes_response, 'Nodes')
    history = results(history_response, 'CPU history')
    site_names = []
    devices = []
    for node in nodes:
        site = required(node, 'Site')
        if not isinstance(site, str) or not site.strip():
            raise ValueError('Site must be explicitly mapped to nonempty text.')
        if site not in site_names:
            site_names.append(site)
        devices.append({'id': required(node, 'NodeID'), 'hostname': required(node, 'Caption'),
                        'site_id': site_names.index(site) + 1, 'device_type': required(node, 'DeviceType')})
    metrics = [{'device_id': required(row, 'NodeID'),
                'collected_at': utc_timestamp(required(row, 'DateTime')),
                'cpu_pct': required(row, 'AvgLoad'),
                'memory_pct': required(row, 'AvgPercentMemoryUsed')} for row in history]
    return {'sites': [{'id': i, 'name': name} for i, name in enumerate(site_names, 1)],
            'devices': devices, 'device_metrics': metrics}


def import_orion(nodes_file, history_file, destination):
    responses = []
    for filename in (nodes_file, history_file):
        path = Path(filename)
        if path.stat().st_size > 20_000_000:
            raise ValueError('Each Orion response must be at most 20 MB.')
        responses.append(json.loads(path.read_text()))
    payload = normalize(*responses)
    with tempfile.TemporaryDirectory() as directory:
        normalized = Path(directory) / 'normalized.json'
        normalized.write_text(json.dumps(payload))
        return import_snapshot(normalized, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('nodes', help='Complete Orion.Nodes query response JSON')
    parser.add_argument('history', help='Complete Orion.CPULoad query response JSON')
    parser.add_argument('destination', help='New SQLite snapshot filename')
    args = parser.parse_args()
    try:
        counts = import_orion(args.nodes, args.history, args.destination)
    except (OSError, ValueError) as error:
        parser.exit(2, f'Orion import failed: {error}\n')
    print('Imported Orion-format snapshot: ' + json.dumps(counts))
    print('Offline import only; this does not verify connectivity to a live Orion instance.')


if __name__ == '__main__':
    main()
