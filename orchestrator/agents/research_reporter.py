"""Research Reporter Agent — writes the daily report from the day's activity."""

from __future__ import annotations

from researcher_mcp.config import get_config
from researcher_mcp.tools.budget_tools import EVENT_CLAUDE_PASS

from ..reporting import build_daily_report
from .base import Agent


class ResearchReporterAgent(Agent):
    name = "research-reporter"

    def run(self) -> dict:
        ctx = self.ctx
        use_model = get_config().enable_model_pass and ctx.budget.can(EVENT_CLAUDE_PASS)
        report = build_daily_report(profile=ctx.profile, use_model=use_model)
        if report.get("generated_by") == "claude_model_pass":
            ctx.budget.record(EVENT_CLAUDE_PASS, notes=f"daily_report:{report['date']}")
        ctx.report = report
        c = report["counts"]
        self.log_event(
            "report", f"date {report['date']}",
            "papers="
            f"{c['papers']} ideas={c['ideas']} experiments={c['experiments']} "
            f"runs={c['runs']} by={report.get('generated_by', 'deterministic')}",
            artifact_path=report["path"],
        )
        return {"path": report["path"], "counts": c, "generated_by": report.get("generated_by")}
