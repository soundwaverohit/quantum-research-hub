"""Ideas page — table + idea-card detail."""

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

st.set_page_config(page_title="Ideas · QRH", page_icon="💡", layout="wide")
st.title("💡 Research Ideas")

if not dl.db_ready():
    st.warning("No database yet.")
    st.stop()

df = dl.ideas_df()
st.caption(f"{len(df)} idea(s) — every idea cites at least one source paper.")
if df.empty:
    st.info("No ideas yet. Run the daily loop to generate ideas from ranked papers.")
    st.stop()

st.dataframe(
    df[["Title", "Hypothesis", "Sources", "Novelty", "Feasibility", "Status"]],
    use_container_width=True, hide_index=True,
)

st.divider()
st.subheader("Idea detail")
choice = st.selectbox(
    "Select an idea", df["ID"].tolist(),
    format_func=lambda i: df.loc[df["ID"] == i, "Title"].iloc[0],
)
if choice:
    st.markdown(dl.idea_markdown(choice))
