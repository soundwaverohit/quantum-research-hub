"""Experiment Runner Agent — runs the small CPU smoke experiment safely.

Only ``small`` mode runs autonomously; the underlying runner enforces the
timeout and approval gates. Gated by the ``experiment_run`` budget cap.
"""

from __future__ import annotations

from researcher_mcp.tools import runner_tools
from researcher_mcp.tools.budget_tools import EVENT_EXPERIMENT_RUN

from .base import Agent


class ExperimentRunnerAgent(Agent):
    name = "experiment-runner"

    def run(self) -> dict:
        ctx = self.ctx
        exp_id = getattr(ctx, "experiment_id", None)
        if not exp_id:
            self.log_event("run", "no experiment", "nothing to run")
            return {"ran": False, "reason": "no_experiment"}
        if not ctx.budget.can(EVENT_EXPERIMENT_RUN):
            self.log_event("run", f"profile={ctx.profile}", "experiment_run cap reached; skipping")
            return {"ran": False, "reason": "budget"}

        res = runner_tools.run_experiment(exp_id, mode="small")
        ctx.run_result = res
        status = res.get("status")
        if status == "completed":
            ctx.budget.record(
                EVENT_EXPERIMENT_RUN, runtime=res.get("runtime_seconds", 0.0), notes=exp_id
            )
            self.log_event(
                "run", exp_id,
                f"completed: energy_error={res.get('metrics', {}).get('energy_error')}",
                artifact_path=res.get("logs_path"),
            )
        else:
            self.log_event("run", exp_id, f"{status}: {res.get('error')}",
                           status="error" if status == "failed" else "ok",
                           artifact_path=res.get("logs_path"))
        return {"ran": status == "completed", "status": status}
