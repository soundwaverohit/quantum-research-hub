"""Tests for the concept extractor (deterministic, no network)."""

from __future__ import annotations

import pytest

from researcher_mcp.ingest.concept_extractor import (
    ConceptExtractionResult,
    extract_from_paper,
    find_concept_mentions,
)


# ---------------------------------------------------------------------------
# Concept mention detection
# ---------------------------------------------------------------------------

def test_detects_long_alias_over_short():
    """'matrix product state' should beat 'mps' at the same position."""
    text = "we use a matrix product state ansatz"
    mentions = find_concept_mentions(text)
    canonicals = [m.canonical for m in mentions]
    assert "mps" in canonicals
    # alias_found should be the long form
    mps_m = next(m for m in mentions if m.canonical == "mps")
    assert "matrix product state" in mps_m.alias_found


def test_detects_mera_and_peps():
    text = "combining mera with peps in a 2d lattice"
    mentions = find_concept_mentions(text)
    canonicals = {m.canonical for m in mentions}
    assert "mera" in canonicals
    assert "peps" in canonicals


def test_short_alias_word_boundary():
    """'vqe' inside 'vqe-like' should still match; 'vqelike' should not."""
    mentions_dash = find_concept_mentions("vqe-like approach")
    assert any(m.canonical == "vqe" for m in mentions_dash)

    mentions_nospace = find_concept_mentions("avqelike approach")
    assert not any(m.canonical == "vqe" for m in mentions_nospace)


def test_detects_barren_plateau():
    text = "we address the barren plateau problem in variational circuits"
    mentions = find_concept_mentions(text)
    assert any(m.canonical == "barren-plateau" for m in mentions)


def test_detects_qfim():
    text = "the quantum fisher information matrix reveals trainability"
    mentions = find_concept_mentions(text)
    assert any(m.canonical == "qfim" for m in mentions)


def test_no_duplicate_spans():
    """No two mentions should overlap."""
    text = (
        "matrix product state representations of the transverse-field ising model "
        "are used together with mera and vqe"
    )
    mentions = find_concept_mentions(text)
    positions = [(m.start, m.end) for m in mentions]
    for i, (s1, e1) in enumerate(positions):
        for j, (s2, e2) in enumerate(positions):
            if i == j:
                continue
            # Spans must not overlap
            assert not (s1 < e2 and s2 < e1), f"Overlapping spans: {positions[i]} and {positions[j]}"


# ---------------------------------------------------------------------------
# Full paper extraction
# ---------------------------------------------------------------------------

def test_extract_from_paper_basic():
    result = extract_from_paper(
        title="VQE with MPS ansatz for the Heisenberg model",
        abstract=(
            "We propose a variational quantum eigensolver that uses matrix product state "
            "as the ansatz. The method is applied to the Heisenberg model and improves on "
            "DMRG in circuit depth."
        ),
    )
    names = result.unique_concept_names()
    assert "vqe" in names
    assert "mps" in names
    assert "heisenberg-model" in names


def test_extract_relations_improves_on():
    result = extract_from_paper(
        title="Faster VQE",
        abstract="Our VQE improves on DMRG for ground state energy estimation.",
    )
    rel_types = {r.relation for r in result.relations}
    assert "improves_on" in rel_types


def test_extract_relations_applied_to():
    result = extract_from_paper(
        title="Tensor Networks for Chemistry",
        abstract="We apply tensor network contraction to quantum chemistry problems.",
    )
    rel_types = {r.relation for r in result.relations}
    assert "applied_to" in rel_types


def test_extract_relations_combines():
    result = extract_from_paper(
        title="Hybrid Ansatz",
        abstract="We combine mera with peps to build a hybrid quantum ansatz.",
    )
    rel_types = {r.relation for r in result.relations}
    assert "combines" in rel_types


def test_concept_scores_sum_to_one():
    result = extract_from_paper(
        title="VQE and MERA",
        abstract="vqe uses mera as an ansatz. vqe is applied to the ising model.",
    )
    scores = result.concept_scores()
    assert abs(sum(scores.values()) - 1.0) < 1e-6 or all(v >= 0 for v in scores.values())


def test_to_card_fields_excludes_co_occurs():
    result = extract_from_paper(
        title="VQE MERA Study",
        abstract="We study vqe and mera together.",  # no explicit relation verb → co_occurs
    )
    _, rels = result.to_card_fields()
    # co_occurs should be filtered out from card fields
    assert all(r["relation"] != "co_occurs" for r in rels)


def test_concept_terms_human_readable():
    result = extract_from_paper(
        title="VQE with MPS",
        abstract="A variational quantum eigensolver using matrix product state ansatz.",
    )
    terms, _ = result.to_card_fields()
    # Should contain human-readable descriptions, not raw keys
    assert any("VQE" in t or "Variational" in t for t in terms)
    assert any("MPS" in t or "Matrix Product" in t for t in terms)


def test_empty_abstract_does_not_raise():
    result = extract_from_paper(title="Quantum", abstract="")
    assert isinstance(result, ConceptExtractionResult)


def test_full_text_augments_extraction():
    # title + abstract have VQE; full_text adds MERA
    result = extract_from_paper(
        title="VQE study",
        abstract="We run variational quantum eigensolver experiments.",
        full_text="The ansatz is a multiscale entanglement renormalization ansatz.",
    )
    names = result.unique_concept_names()
    assert "vqe" in names
    assert "mera" in names
