"""Repository: all SQLite reads/writes for the Quantum Research Hub.

Functions here are the *only* place that knows the table layout. Everything
else (tools, agents, dashboard) speaks in terms of the pydantic models in
``models.py``. JSON-encoded columns are transparently (de)serialized.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

from .db import get_connection
from .models import (
    AgentEvent,
    BudgetEvent,
    Experiment,
    ExperimentRun,
    Idea,
    Paper,
    PaperChunk,
)


def _loads(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


# =============================================================================
# Papers
# =============================================================================
def _paper_from_row(row: sqlite3.Row) -> Paper:
    return Paper(
        arxiv_id=row["arxiv_id"],
        title=row["title"],
        authors=_loads(row["authors_json"], []),
        abstract=row["abstract"] or "",
        categories=_loads(row["categories_json"], []),
        published_date=row["published_date"],
        updated_date=row["updated_date"],
        pdf_url=row["pdf_url"],
        pdf_path=row["pdf_path"],
        parsed_text_path=row["parsed_text_path"],
        paper_card_path=row["paper_card_path"],
        relevance_score=row["relevance_score"] or 0.0,
        novelty_score=row["novelty_score"] or 0.0,
        implementation_score=row["implementation_score"] or 0.0,
        recommended_action=row["recommended_action"] or "track",
        status=row["status"] or "discovered",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def upsert_paper(paper: Paper) -> None:
    """Insert or update a paper by arxiv_id (metadata fields)."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO papers (
              arxiv_id, title, authors_json, abstract, categories_json,
              published_date, updated_date, pdf_url, pdf_path, parsed_text_path,
              paper_card_path, relevance_score, novelty_score, implementation_score,
              recommended_action, status, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(arxiv_id) DO UPDATE SET
              title=excluded.title,
              authors_json=excluded.authors_json,
              abstract=excluded.abstract,
              categories_json=excluded.categories_json,
              published_date=excluded.published_date,
              updated_date=excluded.updated_date,
              pdf_url=excluded.pdf_url,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                paper.arxiv_id, paper.title, json.dumps(paper.authors), paper.abstract,
                json.dumps(paper.categories), paper.published_date, paper.updated_date,
                paper.pdf_url, paper.pdf_path, paper.parsed_text_path, paper.paper_card_path,
                paper.relevance_score, paper.novelty_score, paper.implementation_score,
                str(getattr(paper.recommended_action, "value", paper.recommended_action)),
                str(getattr(paper.status, "value", paper.status)),
            ),
        )


def paper_exists(arxiv_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM papers WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        return row is not None


def get_paper(arxiv_id: str) -> Paper | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        return _paper_from_row(row) if row else None


def update_paper_fields(arxiv_id: str, **fields: Any) -> None:
    """Update arbitrary scalar columns on a paper row."""
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = [
        str(getattr(v, "value", v)) if hasattr(v, "value") else v
        for v in fields.values()
    ]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE papers SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE arxiv_id = ?",
            (*vals, arxiv_id),
        )


def list_papers(
    *,
    days: int | None = None,
    min_relevance: float = 0.0,
    status: str | None = None,
    limit: int = 200,
    order_by: str = "relevance_score DESC, published_date DESC",
) -> list[Paper]:
    where = ["1=1"]
    params: list[Any] = []
    if days is not None:
        since = (date.today() - timedelta(days=days)).isoformat()
        where.append("COALESCE(published_date, substr(created_at,1,10)) >= ?")
        params.append(since)
    if min_relevance > 0:
        where.append("relevance_score >= ?")
        params.append(min_relevance)
    if status:
        where.append("status = ?")
        params.append(status)
    sql = (
        f"SELECT * FROM papers WHERE {' AND '.join(where)} "
        f"ORDER BY {order_by} LIMIT ?"
    )
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_paper_from_row(r) for r in rows]


def count_papers_discovered_today() -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM papers WHERE date(created_at) = date('now')"
        ).fetchone()["c"]


# =============================================================================
# Chunks
# =============================================================================
def add_chunks(chunks: list[PaperChunk]) -> int:
    if not chunks:
        return 0
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO paper_chunks
               (arxiv_id, section, chunk_index, chunk_text, token_estimate, embedding_id)
               VALUES (?,?,?,?,?,?)""",
            [
                (c.arxiv_id, c.section, c.chunk_index, c.chunk_text,
                 c.token_estimate, c.embedding_id)
                for c in chunks
            ],
        )
    return len(chunks)


def get_chunks(arxiv_id: str) -> list[PaperChunk]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM paper_chunks WHERE arxiv_id = ? ORDER BY chunk_index",
            (arxiv_id,),
        ).fetchall()
        return [
            PaperChunk(
                id=r["id"], arxiv_id=r["arxiv_id"], section=r["section"],
                chunk_index=r["chunk_index"], chunk_text=r["chunk_text"],
                token_estimate=r["token_estimate"], embedding_id=r["embedding_id"],
            )
            for r in rows
        ]


def count_chunks(arxiv_id: str) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM paper_chunks WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()["c"]


# =============================================================================
# Ideas
# =============================================================================
def _idea_from_row(row: sqlite3.Row) -> Idea:
    # The full idea body (observation, baseline, metric, ...) is stored as a
    # JSON blob in source_arxiv_ids_json so one column carries both the source
    # ids and the rich fields without a schema migration.
    data = _loads(row["source_arxiv_ids_json"], {})
    if isinstance(data, list):  # legacy/simple form: just the id list
        source_ids = data
        body: dict[str, Any] = {}
    else:
        source_ids = data.get("source_arxiv_ids", [])
        body = data
    return Idea(
        id=row["id"],
        title=row["title"],
        hypothesis=row["hypothesis"],
        source_arxiv_ids=source_ids,
        observation=body.get("observation", ""),
        why_it_might_work=body.get("why_it_might_work", ""),
        smallest_experiment=body.get("smallest_experiment", ""),
        baseline=body.get("baseline", ""),
        metric=body.get("metric", ""),
        failure_modes=body.get("failure_modes", []),
        expected_runtime=body.get("expected_runtime", ""),
        novelty_score=row["novelty_score"] or 0.0,
        feasibility_score=row["feasibility_score"] or 0.0,
        expected_compute_cost=row["expected_compute_cost"] or "small",
        status=row["status"] or "proposed",
        idea_card_path=row["idea_card_path"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def upsert_idea(idea: Idea) -> None:
    # Persist the full idea body (observation, baseline, metric, ...) inside the
    # source_arxiv_ids_json column as a structured blob so a single column keeps
    # both the source ids and the rich fields without a schema migration.
    blob = {
        "source_arxiv_ids": idea.source_arxiv_ids,
        "observation": idea.observation,
        "why_it_might_work": idea.why_it_might_work,
        "smallest_experiment": idea.smallest_experiment,
        "baseline": idea.baseline,
        "metric": idea.metric,
        "failure_modes": idea.failure_modes,
        "expected_runtime": idea.expected_runtime,
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ideas (
              id, title, hypothesis, source_arxiv_ids_json, novelty_score,
              feasibility_score, expected_compute_cost, status, idea_card_path, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
              title=excluded.title, hypothesis=excluded.hypothesis,
              source_arxiv_ids_json=excluded.source_arxiv_ids_json,
              novelty_score=excluded.novelty_score,
              feasibility_score=excluded.feasibility_score,
              expected_compute_cost=excluded.expected_compute_cost,
              status=excluded.status, idea_card_path=excluded.idea_card_path,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                idea.id, idea.title, idea.hypothesis, json.dumps(blob),
                idea.novelty_score, idea.feasibility_score, idea.expected_compute_cost,
                str(getattr(idea.status, "value", idea.status)), idea.idea_card_path,
            ),
        )


def get_idea(idea_id: str) -> Idea | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        return _idea_from_row(row) if row else None


def list_ideas(status: str | None = None, limit: int = 200) -> list[Idea]:
    sql = "SELECT * FROM ideas"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY feasibility_score DESC, created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        return [_idea_from_row(r) for r in conn.execute(sql, params).fetchall()]


def update_idea_status(idea_id: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE ideas SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, idea_id),
        )


def count_ideas_created_today() -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM ideas WHERE date(created_at) = date('now')"
        ).fetchone()["c"]


# =============================================================================
# Experiments
# =============================================================================
def _experiment_from_row(row: sqlite3.Row) -> Experiment:
    return Experiment(
        id=row["id"], idea_id=row["idea_id"], title=row["title"],
        hypothesis=row["hypothesis"] or "", status=row["status"] or "proposed",
        folder_path=row["folder_path"], config_path=row["config_path"],
        result_path=row["result_path"], validator_notes_path=row["validator_notes_path"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def upsert_experiment(exp: Experiment) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO experiments (
              id, idea_id, title, hypothesis, status, folder_path,
              config_path, result_path, validator_notes_path, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
              idea_id=excluded.idea_id, title=excluded.title,
              hypothesis=excluded.hypothesis, status=excluded.status,
              folder_path=excluded.folder_path, config_path=excluded.config_path,
              result_path=excluded.result_path,
              validator_notes_path=excluded.validator_notes_path,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                exp.id, exp.idea_id, exp.title, exp.hypothesis,
                str(getattr(exp.status, "value", exp.status)), exp.folder_path,
                exp.config_path, exp.result_path, exp.validator_notes_path,
            ),
        )


def get_experiment(experiment_id: str) -> Experiment | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
        return _experiment_from_row(row) if row else None


def list_experiments(status: str | None = None, limit: int = 200) -> list[Experiment]:
    sql = "SELECT * FROM experiments"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        return [_experiment_from_row(r) for r in conn.execute(sql, params).fetchall()]


def update_experiment_status(experiment_id: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE experiments SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, experiment_id),
        )


# =============================================================================
# Experiment runs
# =============================================================================
def upsert_run(run: ExperimentRun) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO experiment_runs (
              id, experiment_id, status, started_at, finished_at,
              metrics_json, logs_path, error_message
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              status=excluded.status, started_at=excluded.started_at,
              finished_at=excluded.finished_at, metrics_json=excluded.metrics_json,
              logs_path=excluded.logs_path, error_message=excluded.error_message
            """,
            (
                run.id, run.experiment_id, run.status, run.started_at, run.finished_at,
                json.dumps(run.metrics), run.logs_path, run.error_message,
            ),
        )


def get_runs(experiment_id: str) -> list[ExperimentRun]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_runs WHERE experiment_id=? ORDER BY started_at DESC",
            (experiment_id,),
        ).fetchall()
        return [
            ExperimentRun(
                id=r["id"], experiment_id=r["experiment_id"], status=r["status"],
                started_at=r["started_at"], finished_at=r["finished_at"],
                metrics=_loads(r["metrics_json"], {}), logs_path=r["logs_path"],
                error_message=r["error_message"],
            )
            for r in rows
        ]


def latest_run(experiment_id: str) -> ExperimentRun | None:
    runs = get_runs(experiment_id)
    return runs[0] if runs else None


def count_experiments_run_today() -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM experiment_runs WHERE date(started_at) = date('now')"
        ).fetchone()["c"]


# =============================================================================
# Agent events
# =============================================================================
def log_agent_event(event: AgentEvent) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO agent_events
               (agent_name, action, input_summary, output_summary, status,
                cost_estimate_json, artifact_path)
               VALUES (?,?,?,?,?,?,?)""",
            (
                event.agent_name, event.action, event.input_summary,
                event.output_summary, event.status,
                json.dumps(event.cost_estimate), event.artifact_path,
            ),
        )
        return int(cur.lastrowid or 0)


def list_agent_events(limit: int = 200, agent_name: str | None = None) -> list[AgentEvent]:
    sql = "SELECT * FROM agent_events"
    params: list[Any] = []
    if agent_name:
        sql += " WHERE agent_name = ?"
        params.append(agent_name)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [
            AgentEvent(
                id=r["id"], timestamp=r["timestamp"], agent_name=r["agent_name"],
                action=r["action"], input_summary=r["input_summary"] or "",
                output_summary=r["output_summary"] or "", status=r["status"] or "ok",
                cost_estimate=_loads(r["cost_estimate_json"], {}),
                artifact_path=r["artifact_path"],
            )
            for r in rows
        ]


# =============================================================================
# Budget events
# =============================================================================
def log_budget_event(event: BudgetEvent) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO budget_events
               (budget_profile, event_type, estimated_tokens, estimated_cost,
                local_runtime_seconds, notes)
               VALUES (?,?,?,?,?,?)""",
            (
                event.budget_profile, event.event_type, event.estimated_tokens,
                event.estimated_cost, event.local_runtime_seconds, event.notes,
            ),
        )
        return int(cur.lastrowid or 0)


def budget_counts_today() -> dict[str, int]:
    """Count today's budget events grouped by event_type (used to enforce caps)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT event_type, COUNT(*) AS c FROM budget_events
               WHERE date(timestamp) = date('now') GROUP BY event_type"""
        ).fetchall()
        return {r["event_type"]: r["c"] for r in rows}


def list_budget_events(limit: int = 200) -> list[BudgetEvent]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM budget_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            BudgetEvent(
                id=r["id"], timestamp=r["timestamp"], budget_profile=r["budget_profile"],
                event_type=r["event_type"], estimated_tokens=r["estimated_tokens"] or 0,
                estimated_cost=r["estimated_cost"] or 0.0,
                local_runtime_seconds=r["local_runtime_seconds"] or 0.0,
                notes=r["notes"] or "",
            )
            for r in rows
        ]


# =============================================================================
# Date-scoped queries (used by the daily report)
# =============================================================================
def papers_on(d: str) -> list[Paper]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM papers WHERE date(created_at)=? ORDER BY relevance_score DESC", (d,)
        ).fetchall()
        return [_paper_from_row(r) for r in rows]


def ideas_on(d: str) -> list[Idea]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ideas WHERE date(created_at)=? ORDER BY feasibility_score DESC", (d,)
        ).fetchall()
        return [_idea_from_row(r) for r in rows]


def experiments_on(d: str) -> list[Experiment]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiments WHERE date(created_at)=? ORDER BY created_at DESC", (d,)
        ).fetchall()
        return [_experiment_from_row(r) for r in rows]


def runs_on(d: str) -> list[ExperimentRun]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_runs WHERE date(started_at)=? ORDER BY started_at DESC", (d,)
        ).fetchall()
        return [
            ExperimentRun(
                id=r["id"], experiment_id=r["experiment_id"], status=r["status"],
                started_at=r["started_at"], finished_at=r["finished_at"],
                metrics=_loads(r["metrics_json"], {}), logs_path=r["logs_path"],
                error_message=r["error_message"],
            )
            for r in rows
        ]


def agent_events_on(d: str, limit: int = 500) -> list[AgentEvent]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_events WHERE date(timestamp)=? ORDER BY id ASC LIMIT ?",
            (d, limit),
        ).fetchall()
        return [
            AgentEvent(
                id=r["id"], timestamp=r["timestamp"], agent_name=r["agent_name"],
                action=r["action"], input_summary=r["input_summary"] or "",
                output_summary=r["output_summary"] or "", status=r["status"] or "ok",
                cost_estimate=_loads(r["cost_estimate_json"], {}),
                artifact_path=r["artifact_path"],
            )
            for r in rows
        ]


def papers_between(start: str, end: str) -> list[Paper]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM papers
               WHERE date(created_at) BETWEEN date(?) AND date(?)
               ORDER BY relevance_score DESC, created_at ASC""",
            (start, end),
        ).fetchall()
        return [_paper_from_row(r) for r in rows]


def ideas_between(start: str, end: str) -> list[Idea]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM ideas
               WHERE date(created_at) BETWEEN date(?) AND date(?)
               ORDER BY feasibility_score DESC, created_at ASC""",
            (start, end),
        ).fetchall()
        return [_idea_from_row(r) for r in rows]


def experiments_between(start: str, end: str) -> list[Experiment]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM experiments
               WHERE date(created_at) BETWEEN date(?) AND date(?)
               ORDER BY created_at ASC""",
            (start, end),
        ).fetchall()
        return [_experiment_from_row(r) for r in rows]


def runs_between(start: str, end: str) -> list[ExperimentRun]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM experiment_runs
               WHERE date(started_at) BETWEEN date(?) AND date(?)
               ORDER BY started_at ASC""",
            (start, end),
        ).fetchall()
        return [
            ExperimentRun(
                id=r["id"], experiment_id=r["experiment_id"], status=r["status"],
                started_at=r["started_at"], finished_at=r["finished_at"],
                metrics=_loads(r["metrics_json"], {}), logs_path=r["logs_path"],
                error_message=r["error_message"],
            )
            for r in rows
        ]


def agent_events_between(start: str, end: str, limit: int = 1000) -> list[AgentEvent]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM agent_events
               WHERE date(timestamp) BETWEEN date(?) AND date(?)
               ORDER BY id ASC LIMIT ?""",
            (start, end, limit),
        ).fetchall()
        return [
            AgentEvent(
                id=r["id"], timestamp=r["timestamp"], agent_name=r["agent_name"],
                action=r["action"], input_summary=r["input_summary"] or "",
                output_summary=r["output_summary"] or "", status=r["status"] or "ok",
                cost_estimate=_loads(r["cost_estimate_json"], {}),
                artifact_path=r["artifact_path"],
            )
            for r in rows
        ]


def budget_events_between(start: str, end: str, limit: int = 1000) -> list[BudgetEvent]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM budget_events
               WHERE date(timestamp) BETWEEN date(?) AND date(?)
               ORDER BY id ASC LIMIT ?""",
            (start, end, limit),
        ).fetchall()
        return [
            BudgetEvent(
                id=r["id"], timestamp=r["timestamp"], budget_profile=r["budget_profile"],
                event_type=r["event_type"], estimated_tokens=r["estimated_tokens"] or 0,
                estimated_cost=r["estimated_cost"] or 0.0,
                local_runtime_seconds=r["local_runtime_seconds"] or 0.0,
                notes=r["notes"] or "",
            )
            for r in rows
        ]


# =============================================================================
# Dashboard aggregates
# =============================================================================
def overview_counts() -> dict[str, int]:
    """Headline numbers for the dashboard overview page."""
    with get_connection() as conn:
        def scalar(sql: str, params: tuple = ()) -> int:
            return conn.execute(sql, params).fetchone()[0]

        return {
            "papers_total": scalar("SELECT COUNT(*) FROM papers"),
            "papers_today": scalar("SELECT COUNT(*) FROM papers WHERE date(created_at)=date('now')"),
            "papers_high_relevance": scalar("SELECT COUNT(*) FROM papers WHERE relevance_score>=3"),
            "ideas_total": scalar("SELECT COUNT(*) FROM ideas"),
            "experiments_total": scalar("SELECT COUNT(*) FROM experiments"),
            "experiments_validated": scalar("SELECT COUNT(*) FROM experiments WHERE status='validated'"),
            "runs_total": scalar("SELECT COUNT(*) FROM experiment_runs"),
            "agent_events_total": scalar("SELECT COUNT(*) FROM agent_events"),
        }
