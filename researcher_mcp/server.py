"""Researcher MCP server (FastMCP).

Exposes the Quantum Research Hub's bounded tools to Claude Code and any MCP
client. Each tool:

* delegates to the tested functions in ``researcher_mcp.tools`` (one
  implementation shared with the orchestrator),
* validates inputs and returns structured results/errors (never raises across
  the tool boundary),
* logs the call to the ``agent_events`` table under agent name ``mcp``.

Run::

    python -m researcher_mcp.server      # stdio transport (for Claude Code)
"""

from __future__ import annotations

import json
from typing import Any

from .config import get_config
from .logging_utils import get_logger
from .storage import repository as repo
from .storage.models import AgentEvent
from .tools import (
    arxiv_tools,
    budget_tools,
    dashboard_tools,
    experiment_tools,
    idea_tools,
    memory_tools,
    paper_tools,
    runner_tools,
)

log = get_logger("server")

try:
    from mcp.server.fastmcp import FastMCP

    _MCP_AVAILABLE = True
except Exception as exc:  # pragma: no cover - mcp is a declared dependency
    _MCP_AVAILABLE = False
    _IMPORT_ERROR = exc


def _truncate(value: Any, limit: int = 280) -> str:
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _log_call(action: str, inp: dict, out: Any) -> None:
    status = "error" if isinstance(out, dict) and out.get("error") else "ok"
    try:
        repo.log_agent_event(AgentEvent(
            agent_name="mcp", action=action,
            input_summary=_truncate(inp), output_summary=_truncate(out), status=status,
        ))
    except Exception:  # noqa: BLE001 - logging must never break a tool
        pass


def build_server():  # -> FastMCP
    """Construct the FastMCP server with all tools registered."""
    if not _MCP_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            f"The 'mcp' package is required to run the server (import failed: {_IMPORT_ERROR}). "
            f"Install with: pip install 'mcp[cli]'"
        )

    mcp = FastMCP("quantum-research-hub")

    @mcp.tool()
    def search_arxiv(
        query: str = "",
        categories: list[str] | None = None,
        keywords: list[str] | None = None,
        from_date: str = "",
        to_date: str = "",
        max_results: int = 10,
    ) -> dict:
        """Search arXiv for quantum-computing papers by query, categories, keywords, and date range."""
        out = arxiv_tools.search_arxiv(
            query=query or None, categories=categories, keywords=keywords,
            from_date=from_date or None, to_date=to_date or None, max_results=max_results,
        )
        _log_call("search_arxiv", {"query": query, "categories": categories}, out)
        return out

    @mcp.tool()
    def ingest_paper(arxiv_id: str, force: bool = False, download_pdf: bool = False) -> dict:
        """Ingest one arXiv paper: metadata -> chunks -> deterministic paper card -> DB."""
        out = paper_tools.ingest_paper(arxiv_id, force=force, download_pdf=download_pdf)
        _log_call("ingest_paper", {"arxiv_id": arxiv_id}, out)
        return out

    @mcp.tool()
    def get_paper_card(arxiv_id: str) -> dict:
        """Return the compact paper card (scores, methods, claims, possible experiments)."""
        out = paper_tools.get_paper_card(arxiv_id)
        _log_call("get_paper_card", {"arxiv_id": arxiv_id}, {"ok": "error" not in out})
        return out

    @mcp.tool()
    def search_paper_memory(query: str, k: int = 5) -> dict:
        """Search stored paper memory with the configured local retrieval backend."""
        out = memory_tools.search_paper_memory(query, k=k)
        _log_call("search_paper_memory", {"query": query, "k": k}, {"n": len(out.get("results", []))})
        return out

    @mcp.tool()
    def list_recent_papers(days: int = 7, min_relevance: float = 0.0) -> dict:
        """List recently-seen papers, optionally filtered by minimum relevance score."""
        out = paper_tools.list_recent_papers(days=days, min_relevance=min_relevance)
        _log_call("list_recent_papers", {"days": days, "min_relevance": min_relevance}, {"n": out["count"]})
        return out

    @mcp.tool()
    def create_idea(
        title: str,
        hypothesis: str,
        source_arxiv_ids: list[str],
        observation: str = "",
        smallest_experiment: str = "",
        baseline: str = "",
        metric: str = "",
        failure_modes: list[str] | None = None,
        expected_runtime: str = "",
        novelty_score: float = 0.0,
        feasibility_score: float = 0.0,
    ) -> dict:
        """Create a research idea. MUST cite >=1 source arXiv paper (rejected otherwise)."""
        out = idea_tools.create_idea(
            title, hypothesis, source_arxiv_ids, observation=observation,
            smallest_experiment=smallest_experiment, baseline=baseline, metric=metric,
            failure_modes=failure_modes, expected_runtime=expected_runtime,
            novelty_score=novelty_score, feasibility_score=feasibility_score,
        )
        _log_call("create_idea", {"title": title, "sources": source_arxiv_ids}, out)
        return out

    @mcp.tool()
    def list_ideas(status: str = "") -> dict:
        """List research ideas, optionally filtered by status."""
        out = idea_tools.list_ideas(status=status or None)
        _log_call("list_ideas", {"status": status}, {"n": out["count"]})
        return out

    @mcp.tool()
    def create_experiment_from_idea(idea_id: str, mode: str = "small", auto_run: bool = False) -> dict:
        """Create a reproducible experiment folder from an idea (baseline + tests + config + metrics)."""
        out = experiment_tools.create_experiment_from_idea(idea_id, mode=mode, auto_run=auto_run)
        _log_call("create_experiment_from_idea", {"idea_id": idea_id, "mode": mode}, out)
        return out

    @mcp.tool()
    def get_experiment(experiment_id: str) -> dict:
        """Return full experiment detail: metadata, config, latest metrics, validator notes."""
        out = experiment_tools.get_experiment(experiment_id)
        _log_call("get_experiment", {"experiment_id": experiment_id}, {"ok": "error" not in out})
        return out

    @mcp.tool()
    def list_experiments(status: str = "") -> dict:
        """List experiments with latest metric + validator verdict."""
        out = experiment_tools.list_experiments(status=status or None)
        _log_call("list_experiments", {"status": status}, {"n": out["count"]})
        return out

    @mcp.tool()
    def run_experiment(experiment_id: str, mode: str = "small", approve: bool = False) -> dict:
        """Run an experiment safely (small=autonomous; gpu/medium/long need approval). Timeout-bounded."""
        out = runner_tools.run_experiment(experiment_id, mode=mode, approve=approve)
        _log_call("run_experiment", {"experiment_id": experiment_id, "mode": mode}, out)
        return out

    @mcp.tool()
    def get_experiment_results(experiment_id: str) -> dict:
        """Return the latest run's status, metrics, and log path for an experiment."""
        out = runner_tools.get_experiment_results(experiment_id)
        _log_call("get_experiment_results", {"experiment_id": experiment_id}, {"ok": "error" not in out})
        return out

    @mcp.tool()
    def validate_experiment(experiment_id: str) -> dict:
        """Skeptically validate an experiment; verdict accepted|rejected|inconclusive."""
        out = experiment_tools.validate_experiment(experiment_id)
        _log_call("validate_experiment", {"experiment_id": experiment_id}, out)
        return out

    @mcp.tool()
    def create_daily_report(date: str = "") -> dict:
        """Generate the daily research report markdown for a date (default: today)."""
        from orchestrator.reporting import build_daily_report  # lazy import

        out = build_daily_report(date or None)
        _log_call("create_daily_report", {"date": date}, {"path": out.get("path")})
        return out

    @mcp.tool()
    def create_weekly_report(week_start: str = "") -> dict:
        """Generate the weekly research report markdown (week_start normalized to Monday)."""
        from orchestrator.reporting import build_weekly_report  # lazy import

        out = build_weekly_report(week_start or None)
        _log_call("create_weekly_report", {"week_start": week_start}, {"path": out.get("path")})
        return out

    @mcp.tool()
    def get_budget_status(profile: str = "") -> dict:
        """Return the active budget profile, daily caps, and usage so far today."""
        out = budget_tools.get_budget_status(profile or None)
        _log_call("get_budget_status", {"profile": profile}, {"profile": out["profile"]})
        return out

    @mcp.tool()
    def get_overview() -> dict:
        """Return dashboard headline counts, recent activity, and budget status."""
        out = dashboard_tools.get_overview()
        _log_call("get_overview", {}, {"counts": out["counts"]})
        return out

    return mcp


def main() -> int:
    """Entry point: start the MCP server over stdio."""
    if not _MCP_AVAILABLE:  # pragma: no cover
        print(
            "ERROR: the 'mcp' package is not installed. Install with: pip install 'mcp[cli]'",
        )
        return 1
    get_config().ensure_dirs()
    log.info("Starting Researcher MCP server (stdio)…")
    server = build_server()
    server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
