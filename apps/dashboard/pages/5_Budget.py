"""Budget page — caps vs usage and the budget event log."""

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

st.set_page_config(page_title="Budget · QRH", page_icon="📊", layout="wide")
st.title("📊 Budget")
st.caption("Daily caps protect Claude usage and local compute. Usage is recorded per action.")

if not dl.db_ready():
    st.warning("No database yet.")
    st.stop()

profile = st.selectbox("Profile", ["low", "medium", "high"], index=0)
status, bdf = dl.budget_view(profile)

st.subheader(f"Caps vs usage today — profile `{status['profile']}`")
st.dataframe(bdf, use_container_width=True, hide_index=True)
if not bdf.empty:
    st.bar_chart(bdf.set_index("Resource")[["Used", "Cap"]])

st.divider()
st.subheader("Budget event log")
edf = dl.budget_events_df(limit=200)
if edf.empty:
    st.info("No budget events recorded yet.")
else:
    st.dataframe(edf, use_container_width=True, hide_index=True)
