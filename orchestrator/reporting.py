"""Daily / weekly report generation (Research Reporter capability).

Reads the DB for a given date and renders the markdown report defined in
CLAUDE.md §13 to ``data/reports/daily/<date>.md``. Pure data-in/markdown-out so
it is callable from the orchestrator agent, the daily run, and the MCP
``create_daily_report`` tool.
"""

from __future__ import annotations

from collections import Counter
from datetime import date as date_cls, timedelta
from typing import Any

from researcher_mcp.config import get_config
from researcher_mcp.logging_utils import get_logger
from researcher_mcp.model_pass import ModelPassError, complete_prompt_json
from researcher_mcp.storage import repository as repo
from researcher_mcp.tools.budget_tools import get_budget_status

log = get_logger("orchestrator.reporting")


def _today() -> str:
    return date_cls.today().isoformat()


def _week_start_for(d: date_cls) -> date_cls:
    return d - timedelta(days=d.weekday())


def _parse_date(value: str | None) -> date_cls:
    return date_cls.fromisoformat(value) if value else date_cls.today()


def _action(p) -> str:  # noqa: ANN001
    return str(getattr(p.recommended_action, "value", p.recommended_action))


def _theme_counts(papers) -> Counter[str]:  # noqa: ANN001
    cfg = get_config()
    counts: Counter[str] = Counter()
    for paper in papers:
        text = f"{paper.title} {paper.abstract}".lower()
        for group, keywords in cfg.keyword_groups.items():
            if any(k in text for k in keywords):
                counts[group] += 1
    return counts


def _model_refined_report(payload: dict[str, Any]) -> str | None:
    try:
        data = complete_prompt_json(
            "daily_report.md",
            payload,
            system=(
                "You are a concise quantum-computing research chief of staff. "
                "Rewrite daily lab reports without adding unsupported claims."
            ),
        )
    except ModelPassError as exc:
        log.warning("daily report model pass skipped: %s", exc)
        return None
    markdown = str(data.get("markdown") or "").strip()
    if not markdown.startswith("#") or len(markdown) < 200:
        log.warning("daily report model pass returned unusable markdown")
        return None
    return markdown


def build_daily_report(
    report_date: str | None = None,
    profile: str | None = None,
    *,
    use_model: bool | None = None,
) -> dict:
    """Build (and persist) the daily research report for ``report_date``.

    Returns ``{date, path, markdown, counts}``.
    """
    d = report_date or _today()
    cfg = get_config()

    papers = repo.papers_on(d)
    high = [p for p in papers if p.relevance_score >= 3.0]
    ideas = repo.ideas_on(d)
    experiments = repo.experiments_on(d)
    runs = repo.runs_on(d)
    events = repo.agent_events_on(d)
    budget = get_budget_status(profile)

    def paper_line(p) -> str:
        return (f"- **{p.title}** ([{p.arxiv_id}](https://arxiv.org/abs/{p.arxiv_id})) — "
                f"rel {p.relevance_score}, nov {p.novelty_score}, action `{_action(p)}`")

    high_md = "\n".join(paper_line(p) for p in sorted(high, key=lambda x: -x.relevance_score)[:10]) or "- (none today)"
    papers_md = "\n".join(paper_line(p) for p in papers[:15]) or "- (none discovered today)"

    ideas_md = "\n".join(
        f"- **{i.title}** — _{i.hypothesis}_ (sources: "
        f"{', '.join(i.source_arxiv_ids) or 'n/a'}; feasibility {i.feasibility_score})"
        for i in ideas
    ) or "- (no new ideas today)"

    exp_md = "\n".join(
        f"- `{e.id}` — {e.title} (status: {getattr(e.status, 'value', e.status)})"
        for e in experiments
    ) or "- (no experiments proposed today)"

    runs_md = "\n".join(
        f"- `{r.experiment_id}` — {r.status}"
        + (f", energy_error={r.metrics.get('energy_error')}" if r.metrics else "")
        for r in runs
    ) or "- (no experiments run today)"

    # Validator outcomes derived from experiment status of today's experiments.
    validated = [e for e in experiments if str(getattr(e.status, "value", e.status)) == "validated"]
    rejected = [e for e in experiments if str(getattr(e.status, "value", e.status)) == "rejected"]
    val_md = (
        "\n".join([f"- ✅ `{e.id}` accepted" for e in validated]
                  + [f"- ❌ `{e.id}` rejected" for e in rejected])
        or "- (no validator verdicts today)"
    )

    used = budget["used"]
    budget_md = "\n".join(
        f"- {k}: {used.get(k, 0)} / {budget['caps'].get(k)}" for k in budget["caps"]
    )

    # Recommended next action — simple, honest heuristic.
    if high:
        next_action = (
            f"Review the {len(high)} high-relevance paper(s); the top idea is "
            f"\"{ideas[0].title}\"." if ideas else
            f"Review the {len(high)} high-relevance paper(s) and draft an idea."
        )
    elif papers:
        next_action = "No high-relevance papers today; keep tracking and widen keywords if this persists."
    else:
        next_action = "No new papers ingested today; check arXiv connectivity or widen the date window."

    summary = (
        f"Discovered {len(papers)} paper(s) ({len(high)} high-relevance), generated "
        f"{len(ideas)} idea(s), proposed {len(experiments)} experiment(s), ran {len(runs)}, "
        f"under the **{budget['profile']}** budget. {len(events)} agent action(s) logged."
    )

    md = f"""# Daily Quantum Research Report: {d}

## Summary

{summary}

## Papers Discovered

{papers_md}

## Highest-Relevance Papers

{high_md}

## New Ideas

{ideas_md}

## Experiments Proposed

{exp_md}

## Experiments Run

{runs_md}

## Validator Results

{val_md}

## Budget Usage

Profile: **{budget['profile']}**

{budget_md}

## Recommended Next Action

{next_action}

---
*Generated by the Quantum Research Hub orchestrator (Research Reporter).*
"""

    generated_by = "deterministic"
    should_use_model = get_config().enable_model_pass if use_model is None else use_model
    if should_use_model:
        model_md = _model_refined_report({
            "date": d,
            "deterministic_report": md,
            "counts": {
                "papers": len(papers),
                "high_relevance": len(high),
                "ideas": len(ideas),
                "experiments": len(experiments),
                "runs": len(runs),
                "events": len(events),
            },
            "top_papers": [
                {
                    "arxiv_id": p.arxiv_id,
                    "title": p.title,
                    "relevance_score": p.relevance_score,
                    "novelty_score": p.novelty_score,
                    "recommended_action": _action(p),
                }
                for p in sorted(papers, key=lambda x: -x.relevance_score)[:8]
            ],
            "ideas": [
                {
                    "id": i.id,
                    "title": i.title,
                    "hypothesis": i.hypothesis,
                    "source_arxiv_ids": i.source_arxiv_ids,
                    "feasibility_score": i.feasibility_score,
                }
                for i in ideas[:8]
            ],
            "experiments": [
                {
                    "id": e.id,
                    "title": e.title,
                    "status": str(getattr(e.status, "value", e.status)),
                }
                for e in experiments[:8]
            ],
            "runs": [
                {
                    "experiment_id": r.experiment_id,
                    "status": r.status,
                    "metrics": r.metrics,
                }
                for r in runs[:8]
            ],
            "budget": budget,
        })
        if model_md:
            md = model_md + "\n"
            generated_by = "claude_model_pass"

    cfg.daily_reports_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.daily_reports_dir / f"{d}.md"
    path.write_text(md, encoding="utf-8")
    return {
        "date": d,
        "path": str(path),
        "markdown": md,
        "counts": {
            "papers": len(papers), "high_relevance": len(high), "ideas": len(ideas),
            "experiments": len(experiments), "runs": len(runs), "events": len(events),
        },
        "generated_by": generated_by,
    }


def build_weekly_report(week_start: str | None = None, profile: str | None = None) -> dict:
    """Build and persist a weekly research report.

    ``week_start`` is a Monday ISO date. If omitted, the current week's Monday
    is used. The report covers Monday through Sunday inclusive.
    """
    cfg = get_config()
    start_date = _week_start_for(_parse_date(week_start))
    end_date = start_date + timedelta(days=6)
    start = start_date.isoformat()
    end = end_date.isoformat()

    papers = repo.papers_between(start, end)
    high = [p for p in papers if p.relevance_score >= 3.0]
    ideas = repo.ideas_between(start, end)
    experiments = repo.experiments_between(start, end)
    runs = repo.runs_between(start, end)
    events = repo.agent_events_between(start, end)
    budget_events = repo.budget_events_between(start, end)
    budget = get_budget_status(profile)

    theme_counts = _theme_counts(papers)
    themes_md = "\n".join(
        f"- {theme}: {count} paper(s)" for theme, count in theme_counts.most_common()
    ) or "- (no dominant themes detected)"

    top_papers_md = "\n".join(
        f"- **{p.title}** ([{p.arxiv_id}](https://arxiv.org/abs/{p.arxiv_id})) "
        f"- rel {p.relevance_score}, action `{_action(p)}`"
        for p in sorted(papers, key=lambda x: -x.relevance_score)[:12]
    ) or "- (no papers this week)"

    ideas_md = "\n".join(
        f"- **{i.title}** - feasibility {i.feasibility_score}; "
        f"sources: {', '.join(i.source_arxiv_ids) or 'n/a'}"
        for i in ideas[:12]
    ) or "- (no ideas this week)"

    experiments_md = "\n".join(
        f"- `{e.id}` - {e.title} (status: {getattr(e.status, 'value', e.status)})"
        for e in experiments
    ) or "- (no experiments proposed this week)"

    runs_md = "\n".join(
        f"- `{r.experiment_id}` - {r.status}"
        + (f", energy_error={r.metrics.get('energy_error')}" if r.metrics else "")
        for r in runs
    ) or "- (no experiments run this week)"

    verdict_counts = Counter(str(getattr(e.status, "value", e.status)) for e in experiments)
    verdict_md = "\n".join(
        f"- {status}: {count}" for status, count in sorted(verdict_counts.items())
    ) or "- (no validator outcomes this week)"

    budget_counts = Counter(e.event_type for e in budget_events)
    budget_md = "\n".join(
        f"- {event_type}: {count}" for event_type, count in sorted(budget_counts.items())
    ) or "- (no budget events this week)"

    if experiments:
        next_action = "Pick the strongest validated or inconclusive experiment and define one scale-up test."
    elif ideas:
        next_action = "Promote the most feasible sourced idea into a small experiment."
    elif high:
        next_action = "Review high-relevance papers and draft one baseline-backed experiment idea."
    else:
        next_action = "Widen the arXiv window or keyword set; no strong weekly signal was captured."

    md = f"""# Weekly Quantum Research Report: {start} to {end}

## Summary

This week captured {len(papers)} paper(s), {len(high)} high-relevance paper(s),
{len(ideas)} idea(s), {len(experiments)} experiment(s), and {len(runs)} run(s).
The system logged {len(events)} agent action(s).

## Theme Map

{themes_md}

## Top Papers

{top_papers_md}

## Ideas

{ideas_md}

## Experiments

{experiments_md}

## Runs

{runs_md}

## Validator Outcomes

{verdict_md}

## Budget Events

Current profile view: **{budget['profile']}**

{budget_md}

## Recommended Next Week Plan

{next_action}

---
*Generated by the Quantum Research Hub orchestrator (Weekly Research Reporter).*
"""

    weekly_dir = cfg.reports_dir / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    path = weekly_dir / f"{start}_to_{end}.md"
    path.write_text(md, encoding="utf-8")
    return {
        "week_start": start,
        "week_end": end,
        "path": str(path),
        "markdown": md,
        "counts": {
            "papers": len(papers),
            "high_relevance": len(high),
            "ideas": len(ideas),
            "experiments": len(experiments),
            "runs": len(runs),
            "events": len(events),
            "budget_events": len(budget_events),
        },
        "generated_by": "deterministic",
    }
