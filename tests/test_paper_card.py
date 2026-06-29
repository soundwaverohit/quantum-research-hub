"""Paper card generation: scoring, schema, extraction, persistence."""

from __future__ import annotations

import json

from researcher_mcp.ingest.paper_card import decide_action, generate_card, save_card
from researcher_mcp.storage.models import Paper, PaperCard, RecommendedAction


def _paper(title: str, abstract: str, cats=None) -> Paper:
    return Paper(arxiv_id="2606.01234", title=title, abstract=abstract,
                 categories=cats or ["quant-ph"], published_date="2026-06-05")


def test_high_relevance_tensor_vqe_paper():
    p = _paper(
        "Adaptive QPEPS-QMERA ansatz for the transverse-field Ising model",
        "We propose a novel hybrid tensor network ansatz combining PEPS and MERA layers "
        "for VQE. We show adaptive depth reduces energy error at fixed parameter count on "
        "a small Ising model benchmark, outperforming a fixed-depth MPS baseline.",
    )
    card = generate_card(p)
    assert isinstance(card, PaperCard)
    assert card.relevance_score >= 4.0
    assert "A_tensor_networks" in card.matched_keyword_groups
    assert "B_vqe" in card.matched_keyword_groups
    assert card.recommended_action in (RecommendedAction.EXTEND, RecommendedAction.REPRODUCE)
    assert "Ising" in card.datasets_or_benchmarks
    assert card.core_contribution.lower().startswith("we propose")
    assert card.claims  # at least one claim extracted


def test_irrelevant_paper_scores_zero():
    p = _paper("A review of classical sorting networks",
               "This survey reviews classical sorting algorithms with no quantum content.",
               cats=["cs.DS"])
    card = generate_card(p)
    assert card.relevance_score < 1.0
    assert card.recommended_action == RecommendedAction.IGNORE


def test_decide_action_thresholds():
    assert decide_action(0.0, 0, 0) == RecommendedAction.IGNORE
    assert decide_action(1.5, 2, 2) == RecommendedAction.TRACK
    assert decide_action(5.0, 4, 2) == RecommendedAction.EXTEND
    assert decide_action(3.0, 2, 3) == RecommendedAction.REPRODUCE


def test_save_card_writes_json_and_md():
    p = _paper("VQE on TFIM", "We study VQE for the Ising model with a tensor network ansatz.")
    card = generate_card(p)
    json_path = save_card(card)
    assert json_path.exists()
    assert json_path.with_suffix(".md").exists()
    data = json.loads(json_path.read_text())
    assert data["arxiv_id"] == "2606.01234"
    assert data["generated_by"] == "deterministic"
