"""Paper Scout Agent — discovers candidate papers from arXiv (no deep reading)."""

from __future__ import annotations

from datetime import date, timedelta

from researcher_mcp.config import get_config
from researcher_mcp.ingest.arxiv_client import ArxivClient
from researcher_mcp.storage import repository as repo
from researcher_mcp.tools.budget_tools import EVENT_PAPER_FETCHED

from .base import Agent


class PaperScoutAgent(Agent):
    name = "paper-scout"

    def run(self) -> dict:
        ctx = self.ctx
        cfg = get_config()
        client = ctx.arxiv_client or ArxivClient(min_interval=cfg.arxiv_min_interval)
        to_d = date.today().isoformat()
        from_d = (date.today() - timedelta(days=ctx.lookback_days)).isoformat()

        try:
            papers = client.search(
                categories=cfg.categories, from_date=from_d, to_date=to_d,
                max_results=ctx.max_results,
            )
        except Exception as exc:  # noqa: BLE001
            self.log_event(
                "discover", f"{from_d}..{to_d}", f"arXiv error: {exc}", status="error"
            )
            ctx.candidates = []
            return {"found": 0, "new": 0, "error": str(exc)}

        new = [p for p in papers if not repo.paper_exists(p.arxiv_id)]
        ctx.candidates = new
        ctx.budget.record(EVENT_PAPER_FETCHED, notes=f"{len(papers)} fetched, {len(new)} new")
        self.log_event(
            "discover",
            f"cats={len(cfg.categories)} window {from_d}..{to_d}",
            f"{len(papers)} found, {len(new)} new (deduped)",
            cost_estimate={"papers_fetched": len(papers)},
        )
        return {"found": len(papers), "new": len(new)}
