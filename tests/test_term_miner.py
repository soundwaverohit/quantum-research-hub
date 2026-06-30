"""Tests for the domain-general term miner."""

from __future__ import annotations

from researcher_mcp.indexing.term_miner import (
    MinedTerm,
    is_promotable,
    mine_document,
    salience,
)


def test_acronym_with_definition():
    terms = mine_document("We use Quantum Phase Estimation (QPE) throughout.")
    assert "quantum phase estimation" in terms
    assert terms["quantum phase estimation"].acronym == "QPE"


def test_suffix_noun_phrase_typed():
    terms = mine_document("A hybrid tensor network model is introduced.")
    hits = [t for t in terms if t.endswith("model")]
    assert hits, f"no *-model phrase found in {list(terms)}"
    assert terms[hits[0]].inferred_type == "model"


def test_method_suffix_inference():
    terms = mine_document("We propose a stochastic reconfiguration method for optimization.")
    hits = [t for t in terms if t.endswith("method")]
    assert hits
    assert terms[hits[0]].inferred_type == "method"


def test_leading_determiner_stripped():
    # "the model" should not survive: only the bare head noun remains, too short.
    terms = mine_document("the model was trained.")
    assert "the model" not in terms
    assert "model" not in terms


def test_acronym_stoplist():
    terms = mine_document("THE AND FOR WITH THIS")
    assert not terms  # all are stopword acronyms / determiners


def test_bare_technical_acronym_recorded():
    terms = mine_document("Results using DMRG were strong; DMRG again.")
    assert "dmrg" in terms
    assert terms["dmrg"].count >= 2


def test_salience_monotonic_in_doc_frequency():
    t = MinedTerm(term="tensor renormalization group", display="Tensor Renormalization Group")
    assert salience(t, 5) > salience(t, 2)


def test_promotable_acronym_phrase():
    t = MinedTerm(term="tensor renormalization group", display="x", acronym="TRG", inferred_type="method")
    assert is_promotable(t, doc_frequency=1)


def test_not_promotable_bare_acronym():
    t = MinedTerm(term="xyz", display="XYZ", acronym="XYZ")
    assert not is_promotable(t, doc_frequency=1)


def test_typed_phrase_needs_min_docs():
    t = MinedTerm(term="frustrated spin model", display="x", inferred_type="model")
    assert not is_promotable(t, doc_frequency=2, min_docs=3)
    assert is_promotable(t, doc_frequency=3, min_docs=3)


def test_merge_accumulates_count():
    a = MinedTerm(term="x model", display="x model", count=1)
    b = MinedTerm(term="x model", display="X Model", acronym="XM", count=2)
    a.merge(b)
    assert a.count == 3
    assert a.acronym == "XM"
