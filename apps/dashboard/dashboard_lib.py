"""Shared data-access helpers for the Streamlit dashboard.

The dashboard reads directly from SQLite + artifact files and does NOT require
the MCP server to be running (CLAUDE.md §12). Each page bootstraps sys.path,
then imports this module.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from researcher_mcp.config import get_config
from researcher_mcp.storage import repository as repo
from researcher_mcp.tools.budget_tools import get_budget_status


def db_ready() -> bool:
    cfg = get_config()
    return cfg.db_path.exists()


def _action(obj) -> str:  # noqa: ANN001
    return str(getattr(obj.recommended_action, "value", obj.recommended_action))


def _status(obj) -> str:  # noqa: ANN001
    return str(getattr(obj.status, "value", obj.status))


def papers_df(days: int | None = None, min_relevance: float = 0.0, limit: int = 500) -> pd.DataFrame:
    papers = repo.list_papers(days=days, min_relevance=min_relevance, limit=limit)
    return pd.DataFrame([
        {
            "Date": p.published_date, "Title": p.title, "arXiv ID": p.arxiv_id,
            "Category": ", ".join(p.categories[:2]),
            "Relevance": p.relevance_score, "Novelty": p.novelty_score,
            "Action": _action(p), "Status": _status(p),
        }
        for p in papers
    ])


def ideas_df(limit: int = 500) -> pd.DataFrame:
    ideas = repo.list_ideas(limit=limit)
    return pd.DataFrame([
        {
            "Title": i.title, "Hypothesis": i.hypothesis,
            "Sources": ", ".join(i.source_arxiv_ids), "Novelty": i.novelty_score,
            "Feasibility": i.feasibility_score, "Status": _status(i),
            "ID": i.id,
        }
        for i in ideas
    ])


def experiments_df(limit: int = 500) -> pd.DataFrame:
    from researcher_mcp.tools import experiment_tools

    rows = experiment_tools.list_experiments(limit=limit)["experiments"]
    return pd.DataFrame([
        {
            "Experiment ID": r["id"], "Title": r["title"], "Status": r["status"],
            "Baseline": r["baseline"], "Metric": r["metric"],
            "Best (energy_error)": r["best_result"],
            "Improvement": r["improvement_over_baseline"],
            "Validator": r["validator_verdict"], "Last run": r["last_run"],
        }
        for r in rows
    ])


def agent_events_df(limit: int = 300) -> pd.DataFrame:
    events = repo.list_agent_events(limit=limit)
    return pd.DataFrame([
        {
            "Time": e.timestamp, "Agent": e.agent_name, "Action": e.action,
            "Input": e.input_summary, "Output": e.output_summary,
            "Status": e.status, "Artifact": e.artifact_path or "",
        }
        for e in events
    ])


def budget_view(profile: str | None = None) -> tuple[dict, pd.DataFrame]:
    status = get_budget_status(profile)
    df = pd.DataFrame([
        {
            "Resource": k, "Used": status["used"].get(k, 0),
            "Cap": status["caps"][k], "Remaining": status["remaining"][k],
        }
        for k in status["caps"]
    ])
    return status, df


def budget_events_df(limit: int = 200) -> pd.DataFrame:
    events = repo.list_budget_events(limit=limit)
    return pd.DataFrame([
        {
            "Time": e.timestamp, "Profile": e.budget_profile, "Event": e.event_type,
            "Runtime (s)": e.local_runtime_seconds, "Notes": e.notes,
        }
        for e in events
    ])


def overview() -> dict:
    return repo.overview_counts()


def list_reports(kind: str = "daily") -> list[Path]:
    cfg = get_config()
    d = cfg.reports_dir / "weekly" if kind == "weekly" else cfg.daily_reports_dir
    if not d.exists():
        return []
    return sorted(d.glob("*.md"), reverse=True)


def read_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return f"(could not read {path})"


def paper_card_markdown(arxiv_id: str) -> str:
    cfg = get_config()
    md = cfg.cards_dir / f"{arxiv_id}.md"
    if md.exists():
        return read_text(md)
    return "(no card on disk; the paper may not be ingested yet)"


def idea_markdown(idea_id: str) -> str:
    idea = repo.get_idea(idea_id)
    if idea and idea.idea_card_path and Path(idea.idea_card_path).exists():
        return read_text(Path(idea.idea_card_path))
    return "(no idea card found)"


def experiment_detail(exp_id: str) -> dict:
    from researcher_mcp.tools import experiment_tools

    return experiment_tools.get_experiment(exp_id)
