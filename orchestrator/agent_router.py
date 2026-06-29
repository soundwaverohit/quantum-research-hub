"""Agent router — owns the agent registry, the run context, and the pipeline.

``run_pipeline`` drives the daily sequence (ARCHITECTURE.md §5.2) through the
task queue, instantiating each agent against a shared :class:`RunContext` and
isolating per-agent failures so one bad step never aborts the whole run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from researcher_mcp.logging_utils import get_logger
from researcher_mcp.storage import repository as repo
from researcher_mcp.storage.models import AgentEvent

from .agents.experiment_builder import ExperimentBuilderAgent
from .agents.experiment_runner import ExperimentRunnerAgent
from .agents.idea_generator import IdeaGeneratorAgent
from .agents.paper_curator import PaperCuratorAgent
from .agents.paper_scout import PaperScoutAgent
from .agents.paper_summarizer import PaperSummarizerAgent
from .agents.research_reporter import ResearchReporterAgent
from .agents.validator_critic import ValidatorCriticAgent
from .task_queue import Task, TaskQueue

if TYPE_CHECKING:
    from researcher_mcp.ingest.arxiv_client import ArxivClient
    from researcher_mcp.storage.models import Idea, Paper

    from .budget_manager import BudgetManager

log = get_logger("orchestrator.router")


@dataclass
class RunContext:
    """Shared state threaded through the daily pipeline."""

    profile: str
    budget: "BudgetManager"
    arxiv_client: "ArxivClient | None" = None
    lookback_days: int = 2
    max_results: int = 50
    create_experiments: bool = True

    # Accumulators written by agents as the pipeline progresses.
    candidates: list["Paper"] = field(default_factory=list)
    ingested: list[str] = field(default_factory=list)
    ranked: list["Paper"] = field(default_factory=list)
    promote: list["Paper"] = field(default_factory=list)
    idea_ids: list[str] = field(default_factory=list)
    experiment_id: str | None = None
    run_result: dict | None = None
    validation: dict | None = None
    report: dict | None = None
    results: dict[str, Any] = field(default_factory=dict)


# Registry + canonical pipeline order.
AGENTS = {
    PaperScoutAgent.name: PaperScoutAgent,
    PaperSummarizerAgent.name: PaperSummarizerAgent,
    PaperCuratorAgent.name: PaperCuratorAgent,
    IdeaGeneratorAgent.name: IdeaGeneratorAgent,
    ExperimentBuilderAgent.name: ExperimentBuilderAgent,
    ExperimentRunnerAgent.name: ExperimentRunnerAgent,
    ValidatorCriticAgent.name: ValidatorCriticAgent,
    ResearchReporterAgent.name: ResearchReporterAgent,
}

PIPELINE = list(AGENTS.keys())


def run_pipeline(ctx: RunContext, pipeline: list[str] | None = None) -> RunContext:
    """Run the agent pipeline against ``ctx``, returning the populated context."""
    queue = TaskQueue(Task(name=n) for n in (pipeline or PIPELINE))
    while queue:
        task = queue.dequeue()
        assert task is not None
        agent_cls = AGENTS.get(task.name)
        if agent_cls is None:
            log.warning("unknown agent %s; skipping", task.name)
            continue
        agent = agent_cls(ctx)
        try:
            ctx.results[task.name] = agent.run()
        except Exception as exc:  # noqa: BLE001 - isolate per-agent failures
            log.exception("agent %s failed", task.name)
            ctx.results[task.name] = {"error": str(exc)}
            repo.log_agent_event(AgentEvent(
                agent_name=task.name, action="run",
                output_summary=f"unhandled error: {exc}", status="error",
            ))
    return ctx
