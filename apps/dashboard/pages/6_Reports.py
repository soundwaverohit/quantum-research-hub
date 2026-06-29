"""Reports page — browse and read daily / weekly research reports."""

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

st.set_page_config(page_title="Reports · QRH", page_icon="📝", layout="wide")
st.title("📝 Research Reports")

kind = st.radio("Report type", ["daily", "weekly"], horizontal=True)
reports = dl.list_reports(kind or "daily")
if not reports:
    st.info(
        "No reports yet. Generate daily reports with "
        "`python -m orchestrator.daily_run --profile low` or weekly reports with "
        "`python -m orchestrator.scheduler weekly --profile low`."
    )
    st.stop()

names = [r.stem for r in reports]
pick = st.selectbox(f"{kind.title()} report", names)
chosen = reports[names.index(pick)]
st.download_button("Download .md", dl.read_text(chosen), file_name=chosen.name)
st.divider()
st.markdown(dl.read_text(chosen))
