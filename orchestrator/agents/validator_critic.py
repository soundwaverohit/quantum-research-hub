"""Validator / Critic Agent — skeptically reviews the run and assigns a verdict."""

from __future__ import annotations

from researcher_mcp.tools import experiment_tools

from .base import Agent


class ValidatorCriticAgent(Agent):
    name = "validator-critic"

    def run(self) -> dict:
        ctx = self.ctx
        exp_id = getattr(ctx, "experiment_id", None)
        if not exp_id:
            self.log_event("validate", "no experiment", "nothing to validate")
            return {"validated": False, "reason": "no_experiment"}

        res = experiment_tools.validate_experiment(exp_id)
        if res.get("error"):
            self.log_event("validate", exp_id, f"error: {res['error']}", status="error")
            return {"validated": False, "reason": res["error"]}

        ctx.validation = res
        failed = [k for k, v in res.get("checks", {}).items() if not v]
        self.log_event(
            "validate", exp_id,
            f"verdict={res['verdict']}; failed_checks={failed or 'none'}",
            status="ok",
        )
        return {"validated": True, "verdict": res["verdict"]}
