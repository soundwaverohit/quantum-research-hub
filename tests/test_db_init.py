"""DB initialization + repository round-trip."""

from __future__ import annotations

from researcher_mcp.storage import repository as repo
from researcher_mcp.storage.db import init_db, table_counts
from researcher_mcp.storage.models import AgentEvent, BudgetEvent, Paper


def test_tables_exist_after_init():
    counts = table_counts()
    for t in ("papers", "paper_chunks", "ideas", "experiments",
              "experiment_runs", "agent_events", "budget_events"):
        assert counts[t] == 0, f"{t} should exist and be empty"


def test_paper_roundtrip():
    p = Paper(
        arxiv_id="2606.00001", title="Test", authors=["A. B"],
        abstract="tensor network vqe", categories=["quant-ph"],
        published_date="2026-06-05", relevance_score=4.0,
    )
    repo.upsert_paper(p)
    assert repo.paper_exists("2606.00001")
    got = repo.get_paper("2606.00001")
    assert got is not None and got.title == "Test"
    assert got.authors == ["A. B"]
    assert got.categories == ["quant-ph"]

    # upsert is idempotent + updates
    p.title = "Test v2"
    repo.upsert_paper(p)
    assert repo.get_paper("2606.00001").title == "Test v2"
    assert len(repo.list_papers()) == 1


def test_update_fields_and_recent_filter():
    repo.upsert_paper(Paper(arxiv_id="2606.00002", title="X", published_date="2026-06-05"))
    repo.update_paper_fields("2606.00002", relevance_score=5.0, status="carded")
    assert repo.get_paper("2606.00002").relevance_score == 5.0
    high = repo.list_papers(min_relevance=4.5)
    assert [p.arxiv_id for p in high] == ["2606.00002"]


def test_event_logging_and_counts():
    repo.log_agent_event(AgentEvent(agent_name="t", action="a", output_summary="ok"))
    repo.log_budget_event(BudgetEvent(budget_profile="low", event_type="paper_ingested"))
    assert len(repo.list_agent_events()) == 1
    assert repo.budget_counts_today().get("paper_ingested") == 1


def test_reset_clears_with_child_rows(isolated_env):
    # Reproduce the FK-drop-order bug: parent papers + child chunks + runs present.
    from researcher_mcp.ingest.chunker import make_chunks
    from researcher_mcp.storage.db import reset_db

    repo.upsert_paper(Paper(arxiv_id="2606.00003", title="Y"))
    repo.add_chunks(make_chunks("2606.00003", "some body text here", section="abstract"))
    assert repo.count_chunks("2606.00003") == 1

    reset_db(confirm=True)
    assert table_counts()["papers"] == 0
    assert table_counts()["paper_chunks"] == 0
