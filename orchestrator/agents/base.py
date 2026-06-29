"""Base class for orchestrator agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from researcher_mcp.logging_utils import get_logger
from researcher_mcp.storage import repository as repo
from researcher_mcp.storage.models import AgentEvent

if TYPE_CHECKING:
    from ..agent_router import RunContext


class Agent:
    """An agent owns one step of the daily pipeline.

    Subclasses set ``name`` and implement :meth:`run`, returning a small dict
    summary. Use :meth:`log_event` for every meaningful action so the dashboard
    shows a full audit trail.
    """

    name: str = "agent"

    def __init__(self, ctx: "RunContext") -> None:
        self.ctx = ctx
        self.log = get_logger(f"agent.{self.name}")

    def log_event(
        self, action: str, input_summary: str = "", output_summary: str = "",
        status: str = "ok", cost_estimate: dict[str, Any] | None = None,
        artifact_path: str | None = None,
    ) -> None:
        repo.log_agent_event(AgentEvent(
            agent_name=self.name, action=action, input_summary=input_summary,
            output_summary=output_summary, status=status,
            cost_estimate=cost_estimate or {}, artifact_path=artifact_path,
        ))
        self.log.info("%s | %s", action, (output_summary or "")[:140])

    def run(self) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError
