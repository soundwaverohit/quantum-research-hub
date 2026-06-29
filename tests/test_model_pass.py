"""Optional Claude model-pass utilities."""

from __future__ import annotations

from researcher_mcp.ingest.paper_card import generate_card
from researcher_mcp.model_pass import extract_json_object, render_prompt
from researcher_mcp.storage.models import Paper


class FakeCardClient:
    def complete_json(self, *, system: str, prompt: str, max_tokens: int) -> dict:
        assert "Input JSON:" in prompt
        assert "quantum-computing research assistant" in system
        assert max_tokens > 0
        return {
            "core_contribution": "The paper proposes a structured tensor-network ansatz for VQE.",
            "methods": ["MPS", "VQE", "Structured Ansatz"],
            "claims": ["The method lowers energy error at equal parameter count."],
            "datasets_or_benchmarks": ["TFIM"],
            "relevance_to_user": "Directly relevant to QPEPS-QMERA ansatz comparisons.",
            "possible_experiments": [
                "Compare an MPS-style ansatz against a hardware-efficient ansatz at equal parameter count on a 3-site TFIM using energy error."
            ],
            "relevance_score": 5,
            "novelty_score": 3,
            "implementation_difficulty": 2,
            "recommended_action": "extend",
        }


def test_extract_json_object_from_fenced_response():
    parsed = extract_json_object('Here:\n```json\n{"ok": true, "n": 2}\n```')
    assert parsed == {"ok": True, "n": 2}


def test_render_prompt_appends_input_json():
    prompt = render_prompt("paper_card.md", {"arxiv_id": "2606.01234"})
    assert "Return only a JSON object" in prompt
    assert '"arxiv_id": "2606.01234"' in prompt


def test_generate_card_uses_injected_model_client():
    paper = Paper(
        arxiv_id="2606.01234",
        title="MPS ansatz for VQE on the transverse-field Ising model",
        abstract="We propose a tensor network ansatz for VQE and show lower energy error.",
        categories=["quant-ph"],
    )
    card = generate_card(paper, model_client=FakeCardClient())
    assert card.generated_by == "claude_model_pass"
    assert card.recommended_action.value == "extend"
    assert card.relevance_score == 5.0
    assert card.possible_experiments
