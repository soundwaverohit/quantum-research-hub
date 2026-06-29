"""Daily research run.

Implements the daily sequence from ARCHITECTURE.md §5.2 under a budget profile:
discover -> ingest -> rank -> ideate -> (build -> run -> validate) -> report.

Usage::

    python -m orchestrator.daily_run --profile low
    python -m orchestrator.daily_run --profile medium --lookback-days 3
    python -m orchestrator.daily_run --profile low --offline   # demo without network
"""

from __future__ import annotations

import argparse
import sys

from researcher_mcp.config import BUDGET_PROFILES, get_config
from researcher_mcp.ingest.arxiv_client import ArxivClient
from researcher_mcp.logging_utils import get_logger
from researcher_mcp.storage.db import init_db, table_counts

from .agent_router import RunContext, run_pipeline
from .budget_manager import BudgetManager

log = get_logger("orchestrator.daily_run")


def run_daily(
    profile: str = "low",
    *,
    arxiv_client: ArxivClient | None = None,
    lookback_days: int | None = None,
    max_results: int | None = None,
    create_experiments: bool = True,
) -> dict:
    """Run the full daily pipeline and return a structured summary."""
    cfg = get_config()
    cfg.ensure_dirs()
    # Make the daily run usable even before an explicit `db init`.
    if any(c < 0 for c in table_counts().values()):
        init_db(cfg)

    budget = BudgetManager(profile)
    ctx = RunContext(
        profile=budget.profile,
        budget=budget,
        arxiv_client=arxiv_client,
        lookback_days=lookback_days if lookback_days is not None else cfg.lookback_days,
        max_results=max_results if max_results is not None else cfg.arxiv_max_results,
        create_experiments=create_experiments,
    )
    log.info("Daily run starting (profile=%s, lookback=%dd)", ctx.profile, ctx.lookback_days)
    run_pipeline(ctx)

    return {
        "profile": ctx.profile,
        "results": ctx.results,
        "experiment_id": ctx.experiment_id,
        "validation": ctx.validation,
        "report_path": ctx.report["path"] if ctx.report else None,
        "budget": budget.status(),
    }


def _print_summary(summary: dict) -> None:
    r = summary["results"]
    print("\n=== Quantum Research Hub — daily run summary ===")
    print(f"Profile: {summary['profile']}")
    scout = r.get("paper-scout", {})
    summ = r.get("paper-summarizer", {})
    ideas = r.get("idea-generator", {})
    build = r.get("experiment-builder", {})
    runr = r.get("experiment-runner", {})
    val = r.get("validator-critic", {})
    print(f"Papers: found={scout.get('found', 0)} new={scout.get('new', 0)} "
          f"ingested={summ.get('ingested', 0)}")
    print(f"Ideas created: {ideas.get('ideas_created', 0)}")
    if build.get("created"):
        print(f"Experiment: {summary['experiment_id']} -> run={runr.get('status')} "
              f"verdict={val.get('verdict')}")
    else:
        print(f"Experiment: not created ({build.get('reason', 'n/a')})")
    print(f"Report: {summary['report_path']}")
    rem = summary["budget"]["remaining"]
    print(f"Budget remaining: papers={rem.get('paper_ingested')} ideas={rem.get('idea_created')} "
          f"experiments={rem.get('experiment_created')} runs={rem.get('experiment_run')}")
    if scout.get("error"):
        print(f"NOTE: arXiv fetch error ({scout['error']}). Report still generated.")
    print("================================================\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrator.daily_run", description=__doc__)
    parser.add_argument("--profile", default=None, choices=sorted(BUDGET_PROFILES),
                        help="budget profile (default: config QRH_BUDGET_PROFILE or 'low')")
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--max-results", type=int, default=None)
    parser.add_argument("--no-experiments", action="store_true",
                        help="skip experiment creation/running even if budget allows")
    parser.add_argument("--offline", action="store_true",
                        help="do not call arXiv (demo mode; pipeline still runs + reports)")
    args = parser.parse_args(argv)

    cfg = get_config()
    profile = args.profile or cfg.budget_profile

    client: ArxivClient | None = None
    if args.offline:
        # Inject a no-op client so the scout finds zero candidates without network.
        client = ArxivClient(min_interval=0.0, fetcher=lambda _url: b"<feed></feed>")

    summary = run_daily(
        profile,
        arxiv_client=client,
        lookback_days=args.lookback_days,
        max_results=args.max_results,
        create_experiments=not args.no_experiments,
    )
    _print_summary(summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
