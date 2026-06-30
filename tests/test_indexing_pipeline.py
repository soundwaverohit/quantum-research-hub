"""Tests for the literature indexing pipeline."""

from __future__ import annotations

from researcher_mcp.indexing import pipeline
from researcher_mcp.storage import repository as repo
from researcher_mcp.storage.db import get_connection
from researcher_mcp.storage.models import Paper


def _seed_papers() -> None:
    papers = [
        Paper(arxiv_id="2501.20001",
              title="VQE with MPS ansatz",
              abstract="A variational quantum eigensolver using a matrix product state ansatz "
                       "improves on DMRG. It is applied to the Heisenberg model."),
        Paper(arxiv_id="2501.20002",
              title="Circuit cutting for distributed VQE",
              abstract="Circuit cutting is applied to the Hubbard model and is compared with "
                       "entanglement forging."),
        Paper(arxiv_id="2501.20003",
              title="Tensor Renormalization Group study",
              abstract="The Tensor Renormalization Group (TRG) is applied to the Ising model. "
                       "The Tensor Renormalization Group (TRG) improves on exact diagonalization."),
    ]
    for p in papers:
        repo.upsert_paper(p)


def test_rebuild_index_populates_graph():
    _seed_papers()
    stats = pipeline.rebuild_index(reset=True)
    assert stats["papers"] == 3
    assert stats["evidence"] > 0

    idx = pipeline.get_index_stats()
    assert idx["concepts_seed"] > 0
    assert idx["evidence_rows"] > 0
    assert idx["edges"] > 0


def test_typed_relation_present():
    _seed_papers()
    pipeline.rebuild_index(reset=True)
    idx = pipeline.get_index_stats()
    assert "improves_on" in idx["edges_by_relation"]


def test_reindex_is_idempotent():
    _seed_papers()
    pipeline.rebuild_index(reset=True)
    first = pipeline.get_index_stats()["evidence_rows"]
    pipeline.rebuild_index(reset=True)
    second = pipeline.get_index_stats()["evidence_rows"]
    assert first == second


def test_mined_concept_promoted():
    _seed_papers()  # "Tensor Renormalization Group (TRG)" is NOT in the seed ontology
    pipeline.rebuild_index(reset=True)
    idx = pipeline.get_index_stats()
    assert idx["concepts_mined"] >= 1

    with get_connection() as conn:
        row = conn.execute(
            "SELECT name, source FROM concepts WHERE name='tensor-renormalization-group'"
        ).fetchone()
    assert row is not None
    assert row["source"] == "mined"


def test_mined_concept_linked_to_paper():
    _seed_papers()
    pipeline.rebuild_index(reset=True)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM paper_concepts WHERE concept_name='tensor-renormalization-group'"
        ).fetchone()
    assert row["c"] >= 1


def test_seed_ontology_registered():
    _seed_papers()
    pipeline.rebuild_index(reset=True)
    with get_connection() as conn:
        # A known seed concept and one of its aliases must be present.
        c = conn.execute("SELECT 1 FROM concepts WHERE name='vqe' AND source='seed'").fetchone()
        a = conn.execute("SELECT 1 FROM concept_aliases WHERE alias='vqe'").fetchone()
    assert c is not None and a is not None
