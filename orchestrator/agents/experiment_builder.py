"""Experiment Builder Agent — turns the most feasible idea into an experiment folder.

Gated by the per-day ``experiment_created`` budget cap (0 on the low profile)
and by the ``create_experiments`` flag.
"""

from __future__ import annotations

from researcher_mcp.storage import repository as repo
from researcher_mcp.tools import experiment_tools
from researcher_mcp.tools.budget_tools import EVENT_EXPERIMENT_CREATED

from .base import Agent


class ExperimentBuilderAgent(Agent):
    name = "experiment-builder"

    def run(self) -> dict:
        ctx = self.ctx
        if not ctx.create_experiments:
            self.log_event("build", "disabled", "experiment creation disabled for this run")
            return {"created": False, "reason": "disabled"}
        if not ctx.budget.can(EVENT_EXPERIMENT_CREATED):
            self.log_event(
                "build", f"profile={ctx.profile}",
                "experiment_created cap reached (0 on low profile); skipping",
            )
            return {"created": False, "reason": "budget"}

        idea_ids = getattr(ctx, "idea_ids", [])
        ideas = [repo.get_idea(i) for i in idea_ids]
        ideas = [i for i in ideas if i is not None]
        if not ideas:
            self.log_event("build", "no ideas", "no eligible ideas to build from")
            return {"created": False, "reason": "no_ideas"}

        idea = max(ideas, key=lambda i: i.feasibility_score)
        res = experiment_tools.create_experiment_from_idea(idea.id, mode="small", auto_run=False)
        if res.get("error"):
            self.log_event("build", idea.id, f"failed: {res['error']}", status="error")
            return {"created": False, "reason": res["error"]}

        ctx.experiment_id = res["experiment_id"]
        ctx.budget.record(EVENT_EXPERIMENT_CREATED, notes=res["experiment_id"])
        self.log_event(
            "build", f"idea {idea.id}",
            f"experiment {res['experiment_id']} ({idea.title})",
            artifact_path=res.get("folder_path"),
        )
        return {"created": True, "experiment_id": res["experiment_id"]}
