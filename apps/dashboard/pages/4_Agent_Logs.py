"""Agent Logs page — full audit timeline of every agent/tool action."""

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

st.set_page_config(page_title="Agent Logs · QRH", page_icon="🛰️", layout="wide")
st.title("🛰️ Agent Activity")
st.caption("Every agent and MCP tool action is logged here — the system's audit trail.")

if not dl.db_ready():
    st.warning("No database yet.")
    st.stop()

df = dl.agent_events_df(limit=500)
if df.empty:
    st.info("No agent activity yet. Run the daily loop or call MCP tools.")
    st.stop()

agents = ["(all)"] + sorted(df["Agent"].unique().tolist())
pick = st.selectbox("Filter by agent", agents)
view = df if pick == "(all)" else df[df["Agent"] == pick]

errors = (view["Status"] == "error").sum()
st.caption(f"{len(view)} event(s), {int(errors)} error(s)")
st.dataframe(view, use_container_width=True, hide_index=True)
