"""Paper Summarizer Agent — ingests candidates into compact paper cards.

Builds cards from metadata + abstract (deterministic, no PDF into Claude),
honouring the per-day ingestion cap.
"""

from __future__ import annotations

from researcher_mcp.config import get_config
from researcher_mcp.tools import paper_tools
from researcher_mcp.tools.budget_tools import (
    EVENT_CLAUDE_PASS,
    EVENT_DEEP_SUMMARY,
    EVENT_PAPER_INGESTED,
)

from .base import Agent


class PaperSummarizerAgent(Agent):
    name = "paper-summarizer"

    def run(self) -> dict:
        ctx = self.ctx
        cfg = get_config()
        ingested: list[str] = []
        skipped_budget = 0
        model_refined = 0
        for paper in ctx.candidates:
            if not ctx.budget.can(EVENT_PAPER_INGESTED):
                skipped_budget = len(ctx.candidates) - len(ingested)
                self.log_event(
                    "ingest", "budget cap", "paper_ingested daily cap reached; stopping ingestion"
                )
                break
            use_model = (
                cfg.enable_model_pass
                and ctx.budget.can(EVENT_CLAUDE_PASS)
                and ctx.budget.can(EVENT_DEEP_SUMMARY)
            )
            res = paper_tools.ingest_known_paper(paper, use_model=use_model)
            if res.get("status") == "ingested":
                ingested.append(paper.arxiv_id)
                ctx.budget.record(EVENT_PAPER_INGESTED, notes=paper.arxiv_id)
                if res.get("generated_by") == "claude_model_pass":
                    model_refined += 1
                    ctx.budget.record(EVENT_DEEP_SUMMARY, notes=paper.arxiv_id)
                    ctx.budget.record(EVENT_CLAUDE_PASS, notes=f"paper_card:{paper.arxiv_id}")
                self.log_event(
                    "ingest", paper.arxiv_id,
                    "card built "
                    f"(rel={res.get('relevance_score')}, "
                    f"action={res.get('recommended_action')}, "
                    f"by={res.get('generated_by', 'deterministic')})",
                    artifact_path=res.get("paper_card_path"),
                )
            else:
                self.log_event("ingest", paper.arxiv_id, f"failed: {res.get('error')}", status="error")

        ctx.ingested = ingested
        return {
            "ingested": len(ingested),
            "skipped_for_budget": skipped_budget,
            "model_refined": model_refined,
        }
