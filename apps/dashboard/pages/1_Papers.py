"""Papers page — table + paper-card detail."""

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

st.set_page_config(page_title="Papers · QRH", page_icon="📄", layout="wide")
st.title("📄 Papers")

if not dl.db_ready():
    st.warning("No database yet. Run `python -m researcher_mcp.storage.db init` and seed it.")
    st.stop()

col1, col2, col3 = st.columns(3)
days = col1.selectbox("Window", ["All time", "Last 2 days", "Last 7 days", "Last 30 days"], index=0)
days_map = {"All time": None, "Last 2 days": 2, "Last 7 days": 7, "Last 30 days": 30}
min_rel = col2.slider("Min relevance", 0.0, 5.0, 0.0, 0.5)
col3.write("")

df = dl.papers_df(days=days_map[days], min_relevance=min_rel)
st.caption(f"{len(df)} paper(s)")
if df.empty:
    st.info("No papers match. Try widening the window or running the daily loop.")
    st.stop()

st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Paper card")
choice = st.selectbox(
    "Select a paper", df["arXiv ID"].tolist(),
    format_func=lambda a: f"{a} — {df.loc[df['arXiv ID'] == a, 'Title'].iloc[0][:70]}",
)
if choice:
    st.markdown(dl.paper_card_markdown(choice))
