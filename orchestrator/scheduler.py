"""Very small scheduler.

The MVP is driven by an external scheduler (cron / launchd / a CI job) calling
``python -m orchestrator.daily_run``. This module offers an optional in-process
loop for convenience; it is intentionally minimal and not started by default.

Cron example (07:30 daily, low profile)::

    30 7 * * * cd /path/to/repo && python -m orchestrator.daily_run --profile low

Weekly report example (18:00 Sunday)::

    0 18 * * 0 cd /path/to/repo && python -m orchestrator.scheduler weekly --profile low
"""

from __future__ import annotations

import argparse
import time
from datetime import date as date_cls, timedelta

from researcher_mcp.logging_utils import get_logger

from .daily_run import run_daily
from .reporting import build_weekly_report

log = get_logger("orchestrator.scheduler")


def run_weekly_report(profile: str = "low", week_start: str | None = None) -> dict:
    """Generate one weekly report and return its summary."""
    report = build_weekly_report(week_start=week_start, profile=profile)
    log.info("Weekly report complete: %s", report.get("path"))
    return report


def run_forever(
    profile: str = "low",
    interval_hours: float = 24.0,
    max_iterations: int | None = None,
    *,
    weekly: bool = False,
    weekly_weekday: int = 6,
) -> None:
    """Run the daily pipeline every ``interval_hours`` (blocking).

    ``max_iterations`` bounds the loop (used by tests); ``None`` means forever.
    If ``weekly`` is true, also write one weekly report on ``weekly_weekday``
    (Monday=0, Sunday=6).
    """
    interval = max(60.0, interval_hours * 3600.0)
    i = 0
    last_weekly_start: str | None = None
    while max_iterations is None or i < max_iterations:
        try:
            summary = run_daily(profile)
            log.info("Scheduled run complete: report=%s", summary.get("report_path"))
            today = date_cls.today()
            week_start = (today - timedelta(days=today.weekday())).isoformat()
            if weekly and today.weekday() == weekly_weekday and week_start != last_weekly_start:
                run_weekly_report(profile, week_start=week_start)
                last_weekly_start = week_start
        except Exception:  # noqa: BLE001 - keep the scheduler alive
            log.exception("Scheduled daily run failed")
        i += 1
        if max_iterations is not None and i >= max_iterations:
            break
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrator.scheduler", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    daily = sub.add_parser("daily", help="run one daily pipeline")
    daily.add_argument("--profile", default="low", choices=["low", "medium", "high"])

    weekly = sub.add_parser("weekly", help="write one weekly report")
    weekly.add_argument("--profile", default="low", choices=["low", "medium", "high"])
    weekly.add_argument("--week-start", default=None, help="week date; normalized to that week's Monday")

    loop = sub.add_parser("loop", help="run the in-process scheduler loop")
    loop.add_argument("--profile", default="low", choices=["low", "medium", "high"])
    loop.add_argument("--interval-hours", type=float, default=24.0)
    loop.add_argument("--max-iterations", type=int, default=None)
    loop.add_argument("--weekly", action="store_true", help="also write weekly reports")
    loop.add_argument("--weekly-weekday", type=int, default=6, help="Monday=0, Sunday=6")

    args = parser.parse_args(argv)
    if args.cmd == "daily":
        summary = run_daily(args.profile)
        print(f"Daily report: {summary.get('report_path')}")
    elif args.cmd == "weekly":
        report = run_weekly_report(args.profile, week_start=args.week_start)
        print(f"Weekly report: {report.get('path')}")
    elif args.cmd == "loop":
        run_forever(
            args.profile,
            interval_hours=args.interval_hours,
            max_iterations=args.max_iterations,
            weekly=args.weekly,
            weekly_weekday=args.weekly_weekday,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
