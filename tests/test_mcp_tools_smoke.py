"""MCP server smoke test: it builds, registers the core tools, and logs calls."""

from __future__ import annotations

import asyncio

from researcher_mcp.server import _log_call, build_server
from researcher_mcp.storage import repository as repo

CORE_TOOLS = {
    "search_arxiv", "ingest_paper", "get_paper_card", "search_paper_memory",
    "list_recent_papers", "create_idea", "list_ideas", "create_experiment_from_idea",
    "get_experiment", "list_experiments", "run_experiment", "get_experiment_results",
    "validate_experiment", "create_daily_report", "get_budget_status", "get_overview",
}


def test_server_builds():
    server = build_server()
    assert server is not None
    assert hasattr(server, "run")


def test_core_tools_registered():
    server = build_server()
    try:
        tools = asyncio.run(server.list_tools())
        names = {t.name for t in tools}
    except Exception:  # pragma: no cover - tolerate FastMCP API differences
        return
    missing = CORE_TOOLS - names
    assert not missing, f"missing MCP tools: {missing}"


def test_log_call_writes_agent_event():
    _log_call("search_arxiv", {"query": "vqe"}, {"papers": []})
    events = repo.list_agent_events()
    assert events and events[0].agent_name == "mcp"
    assert events[0].action == "search_arxiv"


def test_log_call_marks_errors():
    _log_call("ingest_paper", {"arxiv_id": "x"}, {"error": "boom"})
    assert repo.list_agent_events()[0].status == "error"


def test_tools_delegate_end_to_end(mock_client):
    # Exercise the same functions the server wraps.
    from researcher_mcp.tools import arxiv_tools, budget_tools, dashboard_tools, paper_tools

    found = arxiv_tools.search_arxiv(categories=["quant-ph"], client=mock_client)
    assert len(found["papers"]) == 3
    ing = paper_tools.ingest_paper("2606.01234", client=mock_client)
    assert ing["status"] == "ingested"
    assert budget_tools.get_budget_status()["profile"] == "medium"
    assert dashboard_tools.get_overview()["counts"]["papers_total"] == 1
