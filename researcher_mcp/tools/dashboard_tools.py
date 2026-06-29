"""Dashboard aggregation tool.

Read-only summary used by both the Streamlit dashboard and the optional
``get_overview`` MCP tool. Pulls only compact rows — never large artifacts.
"""

from __future__ import annotations

from ..storage import repository as repo
from .budget_tools import get_budget_status


def get_overview(profile: str | None = None) -> dict:
    """Return headline counts, recent activity, and budget status for the hub."""
    counts = repo.overview_counts()
    recent_papers = repo.list_papers(limit=8, order_by="created_at DESC")
    recent_events = repo.list_agent_events(limit=10)
    ideas = repo.list_ideas(limit=5)
    experiments = repo.list_experiments(limit=5)
    return {
        "counts": counts,
        "budget": get_budget_status(profile),
        "recent_papers": [
            {"arxiv_id": p.arxiv_id, "title": p.title, "relevance_score": p.relevance_score,
             "recommended_action": str(getattr(p.recommended_action, "value", p.recommended_action))}
            for p in recent_papers
        ],
        "recent_agent_events": [
            {"timestamp": e.timestamp, "agent": e.agent_name, "action": e.action,
             "status": e.status, "output": e.output_summary}
            for e in recent_events
        ],
        "recent_ideas": [{"id": i.id, "title": i.title, "status": str(getattr(i.status, "value", i.status))} for i in ideas],
        "recent_experiments": [
            {"id": e.id, "title": e.title, "status": str(getattr(e.status, "value", e.status))}
            for e in experiments
        ],
    }
