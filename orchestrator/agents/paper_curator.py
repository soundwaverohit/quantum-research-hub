"""Paper Curator Agent — ranks ingested papers by relevance and confirms actions.

Scores are computed deterministically at card time; the curator ranks them,
confirms the recommended action, and marks ranked papers as curated. It is
strict: most papers stay at ``track`` and never become experiments.
"""

from __future__ import annotations

from researcher_mcp.storage import repository as repo
from researcher_mcp.storage.models import PaperStatus

from .base import Agent


class PaperCuratorAgent(Agent):
    name = "paper-curator"

    def run(self) -> dict:
        ctx = self.ctx
        ids = ctx.ingested or [p.arxiv_id for p in ctx.candidates]
        papers = [p for p in (repo.get_paper(a) for a in ids) if p is not None]
        ranked = sorted(papers, key=lambda p: (p.relevance_score, p.novelty_score), reverse=True)

        promote = []  # actions worth turning into ideas
        for p in ranked:
            action = str(getattr(p.recommended_action, "value", p.recommended_action))
            repo.update_paper_fields(p.arxiv_id, status=PaperStatus.CURATED.value)
            if action in ("reproduce", "extend", "summarize") and p.relevance_score >= 3.0:
                promote.append(p)

        ctx.ranked = ranked
        ctx.promote = promote
        top = ", ".join(f"{p.arxiv_id}({p.relevance_score})" for p in ranked[:5]) or "none"
        self.log_event(
            "rank", f"{len(papers)} papers",
            f"top: {top}; {len(promote)} flagged for ideation",
            cost_estimate={"ranked": len(papers)},
        )
        return {"ranked": len(ranked), "flagged": len(promote)}
