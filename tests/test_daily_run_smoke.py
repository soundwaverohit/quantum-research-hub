"""End-to-end daily-run smoke test (network mocked)."""

from __future__ import annotations

from pathlib import Path

from orchestrator.daily_run import run_daily
from orchestrator.reporting import build_weekly_report
from orchestrator.scheduler import run_weekly_report
from researcher_mcp.storage import repository as repo


def test_full_pipeline_medium(today_client):
    summary = run_daily("medium", arxiv_client=today_client, lookback_days=7)
    r = summary["results"]

    # discovery + ingestion (2 relevant + 1 irrelevant in the fixture)
    assert r["paper-scout"]["new"] == 3
    assert r["paper-summarizer"]["ingested"] == 3

    # ranking + ideation (at least one idea, all citing sources)
    assert r["idea-generator"]["ideas_created"] >= 1
    for idea in repo.list_ideas():
        assert idea.source_arxiv_ids, "every idea must cite a source paper"

    # experiment built, run, validated (medium allows 1 each)
    assert summary["experiment_id"] is not None
    assert r["experiment-runner"]["status"] == "completed"
    assert summary["validation"]["verdict"] == "accepted"

    # report written + agent activity logged
    assert summary["report_path"] and Path(summary["report_path"]).exists()
    report = Path(summary["report_path"]).read_text()
    assert "Daily Quantum Research Report" in report
    assert "Budget Usage" in report
    assert len(repo.list_agent_events()) >= 6  # one per pipeline stage at least


def test_low_profile_skips_experiments(today_client):
    summary = run_daily("low", arxiv_client=today_client, lookback_days=7)
    r = summary["results"]
    # low profile caps experiments at 0
    assert summary["experiment_id"] is None
    assert r["experiment-builder"]["created"] is False
    # but it still ingests (cap 5) and reports
    assert r["paper-summarizer"]["ingested"] >= 1
    assert Path(summary["report_path"]).exists()


def test_offline_run_still_reports():
    from researcher_mcp.ingest.arxiv_client import ArxivClient

    empty = ArxivClient(min_interval=0.0, fetcher=lambda _u: b"<feed></feed>")
    summary = run_daily("low", arxiv_client=empty, lookback_days=2)
    assert summary["report_path"] and Path(summary["report_path"]).exists()
    assert summary["results"]["paper-scout"]["new"] == 0


def test_weekly_report_after_daily_run(today_client):
    run_daily("medium", arxiv_client=today_client, lookback_days=7)
    report = build_weekly_report(profile="medium")
    path = Path(report["path"])
    assert path.exists()
    assert "weekly" in path.parts
    text = path.read_text()
    assert "Weekly Quantum Research Report" in text
    assert "Theme Map" in text
    assert report["counts"]["papers"] >= 1


def test_scheduler_weekly_wrapper(today_client):
    run_daily("low", arxiv_client=today_client, lookback_days=7)
    report = run_weekly_report("low")
    assert Path(report["path"]).exists()
    assert report["week_start"] <= report["week_end"]
