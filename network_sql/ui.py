"""Local browser interface; generation and execution are separate actions."""
import csv
import io
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import streamlit as st

from network_sql.source import database_path, dataset_caption
from network_sql.dates import resolve_question
from network_sql.llm import build_messages, generate_sql
from network_sql.executor import execute_query


def clear_answer():
    for key in ("answer", "result", "generation_error", "execution_error"):
        st.session_state.pop(key, None)


def ask_question():
    path = database_path()
    st.title("Ask a question")
    st.write("Ask about network performance. Review the SQL, then explore the results.")
    st.caption(dataset_caption())

    st.text_area("Monitoring question", key="question", on_change=clear_answer,
                 placeholder="Which devices recorded CPU above 80%, and how many samples did each have?")
    st.date_input("Reference date (UTC, optional)", value=None, key="reference_date", on_change=clear_answer,
                  help="Required for today, yesterday, or tomorrow. This sets the date those words refer to.")
    st.caption("Example: with reference date November 4, ‘yesterday’ means November 3 UTC.")
    if st.button("Generate SQL", type="primary"):
        clear_answer()
        question = st.session_state.question.strip()
        reference = st.session_state.reference_date
        reference = reference.isoformat() if reference else None
        if not question:
            st.session_state.generation_error = "Enter a monitoring question first."
        else:
            try:
                resolved = resolve_question(question, reference)
                with closing(sqlite3.connect(path)) as db:
                    messages = build_messages(db, question, reference)
                with st.spinner("Generating SQL…"):
                    sql = generate_sql(messages)
                st.session_state.answer = {"question": question, "resolved_question": resolved, "sql": sql}
            except ValueError as error:
                st.session_state.generation_error = str(error)

    if "generation_error" in st.session_state:
        st.warning(st.session_state.generation_error)
    answer = st.session_state.get("answer")
    if answer is None:
        st.info("Start with a question about CPU, memory, devices, or sites.")
        return
    st.subheader("Review SQL")
    st.write(answer["resolved_question"])
    if answer["sql"].strip() == "UNSUPPORTED":
        st.info("This question needs data or context that is not available. Try a question about the recorded CPU and memory samples.")
        return
    st.code(answer["sql"], language="sql")
    st.caption("Model-generated SQL can answer the wrong question. Review the tables, filters, and date range.")
    if st.button("Run query"):
        st.session_state.pop("result", None)
        st.session_state.pop("execution_error", None)
        try:
            st.session_state.result = execute_query(path, answer["sql"])
        except ValueError as error:
            st.session_state.execution_error = str(error)
    if "execution_error" in st.session_state:
        st.error(st.session_state.execution_error)
    result = st.session_state.get("result")
    if result is not None:
        st.subheader("Results")
        if not result["rows"]:
            st.info("No matching records. Check the date range and filters; an empty result does not imply an outage.")
        else:
            st.dataframe(pd.DataFrame(result["rows"], columns=result["columns"]), hide_index=True)
            st.caption(f"{len(result['rows'])} row(s) returned")
            output = io.StringIO()
            writer = csv.writer(output)
            # Escape spreadsheet formula prefixes in exported text cells.
            def cell(value):
                return "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
            writer.writerow([cell(value) for value in result["columns"]])
            writer.writerows([[cell(value) for value in row] for row in result["rows"]])
            st.download_button("Download CSV", output.getvalue(), "network-results.csv", "text/csv")
        if result["truncated"]:
            st.warning("Showing the first 100 rows. Narrow the question for more focused results.")


def main():
    from network_sql.views import explore_data, evaluation_results

    st.set_page_config(page_title="Network SQL Assistant", page_icon="📡", layout="wide")
    try:
        database_path()
    except (ValueError, sqlite3.Error) as error:
        st.error(str(error))
        st.stop()
    # Retain question widgets when their page is temporarily absent.
    for key in ("question", "reference_date"):
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
    with st.sidebar:
        st.header("Network SQL Assistant")
        st.caption(dataset_caption())
    page = st.navigation([
        st.Page(ask_question, title="Ask a question", icon="💬", default=True),
        st.Page(explore_data, title="Explore data", icon="🗃️", url_path="data"),
        st.Page(evaluation_results, title="Evaluation results", icon="📊", url_path="evaluations"),
    ])
    page.run()


if __name__ == "__main__":
    main()
