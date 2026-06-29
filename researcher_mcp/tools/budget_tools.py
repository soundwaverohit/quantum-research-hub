"""Budget event vocabulary + ``get_budget_status``.

The canonical budget event-type names live here (the lowest layer) so both the
MCP tool and the orchestrator's budget manager share one definition.
"""

from __future__ import annotations

from ..config import BUDGET_PROFILES, get_config
from ..storage import repository as repo

# Canonical budget event types and the profile cap each one counts against.
EVENT_PAPER_FETCHED = "paper_fetched"        # informational (not capped)
EVENT_PAPER_INGESTED = "paper_ingested"
EVENT_DEEP_SUMMARY = "deep_summary"
EVENT_IDEA_CREATED = "idea_created"
EVENT_EXPERIMENT_CREATED = "experiment_created"
EVENT_EXPERIMENT_RUN = "experiment_run"
EVENT_CLAUDE_PASS = "claude_pass"

# event_type -> BudgetProfile attribute holding the daily cap.
CAP_FOR: dict[str, str] = {
    EVENT_PAPER_INGESTED: "max_papers_per_day",
    EVENT_DEEP_SUMMARY: "max_deep_summaries_per_day",
    EVENT_IDEA_CREATED: "max_ideas_per_day",
    EVENT_EXPERIMENT_CREATED: "max_experiments_created_per_day",
    EVENT_EXPERIMENT_RUN: "max_experiments_run_per_day",
    EVENT_CLAUDE_PASS: "max_claude_passes_per_day",
}


def get_budget_status(profile: str | None = None) -> dict:
    """Return the active budget profile, its caps, and today's usage.

    Args:
        profile: Override profile name (``low``/``medium``/``high``). Defaults
            to the configured profile.

    Returns:
        ``{"profile", "caps", "used", "remaining", "events_today"}``.
    """
    cfg = get_config()
    name = (profile or cfg.budget_profile).lower()
    bp = BUDGET_PROFILES.get(name, BUDGET_PROFILES["low"])
    used_counts = repo.budget_counts_today()

    caps: dict[str, int] = {}
    used: dict[str, int] = {}
    remaining: dict[str, int] = {}
    for event_type, attr in CAP_FOR.items():
        cap = getattr(bp, attr)
        u = used_counts.get(event_type, 0)
        caps[event_type] = cap
        used[event_type] = u
        remaining[event_type] = max(0, cap - u)

    return {
        "profile": name,
        "caps": caps,
        "used": used,
        "remaining": remaining,
        "events_today": int(sum(used_counts.values())),
    }
