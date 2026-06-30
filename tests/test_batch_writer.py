"""Tests for the batched indexing writer."""

from __future__ import annotations

from researcher_mcp.indexing.writer import BatchWriter
from researcher_mcp.storage.db import get_connection
from researcher_mcp.storage.models import Paper
from researcher_mcp.storage import repository as repo


def _count(table: str) -> int:
    with get_connection() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_buffered_writes_persist_on_close():
    repo.upsert_paper(Paper(arxiv_id="2501.10001", title="t", abstract="a"))
    with BatchWriter(batch_size=100) as w:
        w.add_concept("vqe", "method", "VQE", ["vqe"])
        w.add_alias("vqe", "vqe")
        w.add_paper_concept("2501.10001", "vqe", 0.5, 3)
        w.add_evidence("2501.10001", "vqe", "dmrg", "improves_on",
                       "VQE improves on DMRG.", 0, 20, "abstract", 0.85)
    assert _count("concepts") == 1
    assert _count("paper_concepts") == 1
    assert _count("relation_evidence") == 1


def test_evidence_insert_is_idempotent():
    with BatchWriter() as w:
        for _ in range(2):  # identical evidence (same unique key) added twice
            w.add_evidence("2501.10002", "a", "b", "improves_on",
                           "A improves on B.", 0, 15, "abstract", 0.8)
    assert _count("relation_evidence") == 1


def test_recompute_builds_edges_from_evidence():
    with BatchWriter() as w:
        w.add_concept("vqe", "method", "VQE", ["vqe"])
        w.add_concept("dmrg", "method", "DMRG", ["dmrg"])
        # Two papers provide the same typed relation.
        w.add_evidence("p1", "vqe", "dmrg", "improves_on", "ev1", 0, 5, "abstract", 0.85)
        w.add_evidence("p2", "vqe", "dmrg", "improves_on", "ev2", 0, 5, "abstract", 0.85)
        w.recompute_aggregates()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT weight, evidence_count, paper_ids_json FROM concept_edges "
            "WHERE source='vqe' AND target='dmrg' AND relation='improves_on'"
        ).fetchone()
    assert row is not None
    assert row["evidence_count"] == 2
    assert abs(row["weight"] - 1.7) < 1e-6  # 0.85 + 0.85
    import json
    assert set(json.loads(row["paper_ids_json"])) == {"p1", "p2"}


def test_recompute_is_idempotent_on_rerun():
    with BatchWriter() as w:
        w.add_concept("a", "method", "A", ["a"])
        w.add_concept("b", "method", "B", ["b"])
        w.add_evidence("p1", "a", "b", "enables", "ev", 0, 5, "abstract", 0.68)
        w.recompute_aggregates()
        w.recompute_aggregates()  # second pass must not duplicate the edge
    with get_connection() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM concept_edges WHERE source='a' AND target='b'"
        ).fetchone()[0]
    assert n == 1


def test_symmetric_relation_direction_normalized():
    with BatchWriter() as w:
        w.add_concept("vqe", "method", "VQE", ["vqe"])
        w.add_concept("dmrg", "method", "DMRG", ["dmrg"])
        # Same symmetric relation written both directions -> one normalized edge.
        w.add_evidence("p1", "vqe", "dmrg", "compared_to", "ev1", 0, 5, "abstract", 0.6)
        w.add_evidence("p2", "dmrg", "vqe", "compared_to", "ev2", 0, 5, "abstract", 0.6)
        w.recompute_aggregates()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT source, target, evidence_count FROM concept_edges WHERE relation='compared_to'"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["evidence_count"] == 2
    assert rows[0]["source"] == "dmrg" and rows[0]["target"] == "vqe"  # sorted


def test_batch_flush_threshold():
    # batch_size=2 forces a mid-stream flush; all rows still land.
    with BatchWriter(batch_size=2) as w:
        for i in range(5):
            w.add_concept(f"c{i}", "method", f"C{i}", [f"c{i}"])
    assert _count("concepts") == 5
