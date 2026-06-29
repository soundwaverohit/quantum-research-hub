"""Budget manager — enforces daily caps and records actual usage.

Caps come from the active :class:`BudgetProfile` (low/medium/high). Usage is
counted from ``budget_events`` rows recorded today, so enforcement survives
process restarts within the same day. The budget manager is the ONE place that
both checks (``can``) and records (``record``) spend — agents never write
budget rows directly.
"""

from __future__ import annotations

from researcher_mcp.config import BUDGET_PROFILES, get_config
from researcher_mcp.logging_utils import get_logger
from researcher_mcp.storage import repository as repo
from researcher_mcp.storage.models import BudgetEvent
from researcher_mcp.tools import budget_tools
from researcher_mcp.tools.budget_tools import CAP_FOR, get_budget_status

log = get_logger("orchestrator.budget")


class BudgetManager:
    def __init__(self, profile: str | None = None) -> None:
        cfg = get_config()
        self.profile = (profile or cfg.budget_profile).lower()
        self.bp = BUDGET_PROFILES.get(self.profile, BUDGET_PROFILES["low"])

    def cap(self, event_type: str) -> int | None:
        attr = CAP_FOR.get(event_type)
        return getattr(self.bp, attr) if attr else None

    def used(self, event_type: str) -> int:
        return repo.budget_counts_today().get(event_type, 0)

    def remaining(self, event_type: str) -> int | None:
        cap = self.cap(event_type)
        return None if cap is None else max(0, cap - self.used(event_type))

    def can(self, event_type: str) -> bool:
        """True if at least one more of ``event_type`` is within today's cap."""
        cap = self.cap(event_type)
        if cap is None:  # uncapped (informational events)
            return True
        return self.used(event_type) < cap

    def record(
        self, event_type: str, *, estimated_tokens: int = 0, estimated_cost: float = 0.0,
        runtime: float = 0.0, notes: str = "",
    ) -> None:
        repo.log_budget_event(BudgetEvent(
            budget_profile=self.profile, event_type=event_type,
            estimated_tokens=estimated_tokens, estimated_cost=estimated_cost,
            local_runtime_seconds=runtime, notes=notes,
        ))

    def status(self) -> dict:
        return get_budget_status(self.profile)


__all__ = ["BudgetManager", "budget_tools"]
