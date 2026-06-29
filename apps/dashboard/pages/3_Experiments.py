"""Experiments page — table + experiment detail (metrics, config, validator notes)."""

from __future__ import annotations

import pathlib
import sys

_here = pathlib.Path(__file__).resolve()
_root = next((p for p in _here.parents if (p / "pyproject.toml").exists()), _here.parents[-1])
for _p in (str(_root), str(_root / "apps" / "dashboard")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

import dashboard_lib as dl

st.set_page_config(page_title="Experiments · QRH", page_icon="🧪", layout="wide")
st.title("🧪 Experiments")

if not dl.db_ready():
    st.warning("No database yet.")
    st.stop()

df = dl.experiments_df()
st.caption(f"{len(df)} experiment(s) — each has a baseline, metric, seed, and validator verdict.")
if df.empty:
    st.info(
        "No experiments yet. Run `python -m orchestrator.daily_run --profile medium` "
        "(the low profile caps experiments at 0) or seed demo data."
    )
    st.stop()

st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Experiment detail")
choice = st.selectbox("Select an experiment", df["Experiment ID"].tolist())
if choice:
    detail = dl.experiment_detail(choice)
    exp = detail.get("experiment", {})
    metrics = detail.get("metrics", {})
    st.write(f"**{exp.get('title')}** — status `{exp.get('status')}`")

    mcol = st.columns(4)
    if metrics:
        mcol[0].metric("Exact energy", metrics.get("exact_energy"))
        mcol[1].metric("VQE energy", metrics.get("vqe_energy"))
        mcol[2].metric("Energy error", metrics.get("energy_error"))
        mcol[3].metric("Improvement", metrics.get("improvement_over_baseline"))
    else:
        st.info("No metrics yet (experiment not run).")

    tabs = st.tabs(["Metrics", "Validator notes", "Config", "Files"])
    with tabs[0]:
        st.json(metrics or {})
    with tabs[1]:
        st.markdown(detail.get("validator_notes") or "_pending_")
    with tabs[2]:
        st.json(detail.get("config") or {})
    with tabs[3]:
        st.write(detail.get("files") or [])
