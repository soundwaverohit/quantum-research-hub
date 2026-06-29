"""Idea registry tools (MCP contracts: ``create_idea``, ``list_ideas``).

HARD CONSTRAINT: every idea must reference at least one source paper. The
``create_idea`` tool rejects ideas with no ``source_arxiv_ids``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import date

from ..config import get_config
from ..logging_utils import get_logger
from ..storage import repository as repo
from ..storage.models import Idea, IdeaStatus

log = get_logger("tools.idea")


def _slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (s[:max_len] or "idea").strip("_")


def new_idea_id(title: str) -> str:
    return f"{date.today():%Y%m%d}_{_slug(title)}_{uuid.uuid4().hex[:6]}"


def _render_idea_markdown(idea: Idea) -> str:
    fm = "\n".join(f"- {m}" for m in idea.failure_modes) or "- (none listed)"
    srcs = "\n".join(f"- [{s}](https://arxiv.org/abs/{s})" for s in idea.source_arxiv_ids)
    return f"""# Idea — {idea.title}

**Status:** {idea.status.value if hasattr(idea.status, 'value') else idea.status} ·
**Novelty:** {idea.novelty_score} · **Feasibility:** {idea.feasibility_score} ·
**Compute:** {idea.expected_compute_cost}

## Source papers
{srcs}

## Observation
{idea.observation or "(n/a)"}

## Hypothesis
{idea.hypothesis}

## Why it might work
{idea.why_it_might_work or "(n/a)"}

## Smallest experiment
{idea.smallest_experiment or "(n/a)"}

## Baseline
{idea.baseline or "(n/a)"}

## Metric
{idea.metric or "(n/a)"}

## Failure modes
{fm}

## Expected runtime
{idea.expected_runtime or "(n/a)"}
"""


def create_idea(
    title: str,
    hypothesis: str,
    source_arxiv_ids: Sequence[str],
    *,
    observation: str = "",
    why_it_might_work: str = "",
    smallest_experiment: str = "",
    baseline: str = "",
    metric: str = "",
    failure_modes: Sequence[str] | None = None,
    expected_runtime: str = "",
    novelty_score: float = 0.0,
    feasibility_score: float = 0.0,
    expected_compute_cost: str = "small",
) -> dict:
    """Create a research idea. Must cite at least one source arXiv paper.

    Returns the created idea dict, or ``{"error": ...}`` if validation fails.
    """
    if not title or not hypothesis:
        return {"error": "title and hypothesis are required"}
    source_arxiv_ids = [s for s in (source_arxiv_ids or []) if s]
    if not source_arxiv_ids:
        return {"error": "an idea must reference at least one source paper (source_arxiv_ids)"}

    idea = Idea(
        id=new_idea_id(title),
        title=title,
        hypothesis=hypothesis,
        source_arxiv_ids=list(source_arxiv_ids),
        observation=observation,
        why_it_might_work=why_it_might_work,
        smallest_experiment=smallest_experiment,
        baseline=baseline,
        metric=metric,
        failure_modes=list(failure_modes or []),
        expected_runtime=expected_runtime,
        novelty_score=novelty_score,
        feasibility_score=feasibility_score,
        expected_compute_cost=expected_compute_cost,
        status=IdeaStatus.PROPOSED,
    )

    cfg = get_config()
    cfg.ideas_dir.mkdir(parents=True, exist_ok=True)
    card_path = cfg.ideas_dir / f"{idea.id}.md"
    card_path.write_text(_render_idea_markdown(idea), encoding="utf-8")
    idea.idea_card_path = str(card_path)

    repo.upsert_idea(idea)
    log.info("Created idea %s (%s)", idea.id, idea.title)
    return idea.model_dump(mode="json")


def list_ideas(status: str | None = None, limit: int = 100) -> dict:
    """List ideas, optionally filtered by status."""
    ideas = repo.list_ideas(status=status, limit=limit)
    return {"count": len(ideas), "ideas": [i.model_dump(mode="json") for i in ideas]}
