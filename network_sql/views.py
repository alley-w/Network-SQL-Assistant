"""Read-only data exploration and saved evaluation reports."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import streamlit as st

from network_sql.executor import execute_query
from network_sql.source import database_path, dataset_caption

ROOT = Path(__file__).resolve().parent.parent


def explore_data():
    path = database_path()
    st.title("Explore data")
    st.write("Each site has devices; each device has hourly CPU and memory samples.")
    st.caption(dataset_caption())
    counts = execute_query(path, "SELECT (SELECT COUNT(*) FROM sites), (SELECT COUNT(*) FROM devices), (SELECT COUNT(*) FROM device_metrics)")["rows"][0]
    for column, label, count in zip(st.columns(3), ("Sites", "Devices", "Samples"), counts):
        column.metric(label, count)
    st.info("A sample is a measurement, not an outage. Interface bandwidth and downtime are not recorded.")
    table = st.selectbox("Table", ["sites", "devices", "device_metrics"])
    queries = {
        "sites": "SELECT * FROM sites ORDER BY id LIMIT 20",
        "devices": "SELECT * FROM devices ORDER BY id LIMIT 20",
        "device_metrics": "SELECT * FROM device_metrics ORDER BY collected_at, device_id LIMIT 20",
    }
    result = execute_query(path, queries[table])
    st.dataframe(pd.DataFrame(result["rows"], columns=result["columns"]), hide_index=True)
    st.caption("Preview: up to 20 rows, ordered by identifier or timestamp.")
    with st.expander("Database schema"):
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
            schema = "\n\n".join(row[0] + ";" for row in db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"))
        st.code(schema, language="sql")


def evaluation_results():
    st.title("Evaluation results")
    st.write("Inspect saved reports, including generated SQL and questions that failed.")
    st.caption("Viewing reports makes no model requests. Baselines are historical runs on small synthetic datasets.")
    candidates = {
        "Development baseline": ROOT / "benchmarks" / "baseline.json",
        "Challenge baseline": ROOT / "benchmarks" / "challenge-baseline.json",
        "Latest development run": Path("data/model-evaluation.json"),
        "Latest challenge run": Path("data/challenge-evaluation.json"),
    }
    available = {label: path for label, path in candidates.items() if path.is_file()}
    if not available:
        st.info("No saved evaluation reports are available yet.")
        return
    selected = st.selectbox("Report", list(available))
    try:
        report = json.loads(available[selected].read_text())
        results = report["results"]
        if not isinstance(results, list):
            raise ValueError("Invalid results")
        passed, total = report["passed"], report["total"]
    except (OSError, ValueError, KeyError, TypeError):
        st.warning("This report could not be read. Generate a new evaluation report and try again.")
        return
    st.metric("Questions passed", f"{passed}/{total}")
    st.caption(f"Model: {report.get('model', 'unspecified')} · Recorded: {report.get('created_at', 'unspecified')}")
    st.info(report.get("scope", "Results on a small synthetic dataset; not a production accuracy estimate."))
    failures_only = st.checkbox("Show failed questions only")
    visible = [r for r in results if not failures_only or r.get("status") != "pass"]
    if not visible:
        st.success("No failed questions in this report.")
    for result in visible:
        with st.expander(f"{result.get('status', 'unknown').upper()} · {result.get('question', result.get('id', 'Question'))}"):
            if result.get("generated_sql"):
                st.code(result["generated_sql"], language="sql")
            st.json({key: value for key, value in result.items() if key != "generated_sql"})
