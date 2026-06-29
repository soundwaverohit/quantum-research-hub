"""Quantum Research Hub — Streamlit dashboard (Overview).

Run from the repo root::

    streamlit run apps/dashboard/Home.py

Reads SQLite + artifact files directly; the MCP server need not be running.
"""

from __future__ import annotations

# --- bootstrap sys.path so `researcher_mcp` + `dashboard_lib` import ----------
import pathlib
import sys

_here = pathlib.Path(__file__).resolve()
_root = next((p for p in _here.parents if (p / "pyproject.toml").exists()), _here.parents[-1])
for _p in (str(_root), str(_root / "apps" / "dashboard")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# ------------------------------------------------------------------------------

import streamlit as st

import dashboard_lib as dl

st.set_page_config(page_title="Quantum Research Hub", page_icon="⚛️", layout="wide")

st.title("⚛️ Quantum Research Hub")
st.caption(
    "Local-first, MCP-powered autonomous research for quantum computing — "
    "papers, ideas, experiments, validation, and budget, all auditable."
)

if not dl.db_ready():
    st.warning(
        "No database found yet. Initialize and seed it:\n\n"
        "```bash\npython -m researcher_mcp.storage.db init\n"
        "python scripts/seed_demo.py\n```"
    )
    st.stop()

counts = dl.overview()
status, budget_df = dl.budget_view()

st.subheader("Today & totals")
c = st.columns(4)
c[0].metric("Papers (total)", counts["papers_total"], delta=f"+{counts['papers_today']} today")
c[1].metric("High-relevance papers", counts["papers_high_relevance"])
c[2].metric("Ideas", counts["ideas_total"])
c[3].metric("Experiments", counts["experiments_total"])
c = st.columns(4)
c[0].metric("Validated results", counts["experiments_validated"])
c[1].metric("Experiment runs", counts["runs_total"])
c[2].metric("Agent actions", counts["agent_events_total"])
c[3].metric("Budget profile", status["profile"])

left, right = st.columns([2, 1])

with left:
    st.subheader("Recent papers")
    pdf = dl.papers_df(limit=10)
    if pdf.empty:
        st.info("No papers yet — run `python -m orchestrator.daily_run --profile low`.")
    else:
        st.dataframe(pdf[["Date", "Title", "Relevance", "Action"]], use_container_width=True, hide_index=True)

    st.subheader("Recent agent activity")
    edf = dl.agent_events_df(limit=12)
    if edf.empty:
        st.info("No agent activity logged yet.")
    else:
        st.dataframe(edf[["Time", "Agent", "Action", "Output", "Status"]], use_container_width=True, hide_index=True)

with right:
    st.subheader("Budget today")
    st.dataframe(budget_df, use_container_width=True, hide_index=True)
    st.subheader("Latest report")
    reports = dl.list_reports()
    if reports:
        st.write(f"**{reports[0].stem}**")
        with st.expander("Preview", expanded=False):
            st.markdown(dl.read_text(reports[0]))
    else:
        st.info("No reports yet.")

st.divider()
st.caption("Use the sidebar pages: Papers · Ideas · Experiments · Agent Logs · Budget · Reports")
