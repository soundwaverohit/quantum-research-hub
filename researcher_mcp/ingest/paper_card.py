"""Deterministic paper-card generation.

Builds the compact :class:`PaperCard` (ARCHITECTURE.md §5.3) from a paper's
metadata + abstract using transparent, reproducible heuristics — no paid API,
no PDF-into-Claude. A clean seam (``generated_by``) is left for an optional
model pass later, but the default and the smoke test are fully deterministic.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..config import KEYWORD_GROUPS, get_config
from ..logging_utils import get_logger
from ..model_pass import JsonModelClient, ModelPassError, complete_prompt_json
from ..storage.models import Paper, PaperCard, RecommendedAction
from .concept_extractor import extract_from_paper

log = get_logger("ingest.paper_card")

# Human-readable framing of each keyword group w.r.t. the user's agenda.
GROUP_RELEVANCE: dict[str, str] = {
    "A_tensor_networks": "tensor-network ansätze (MPS/PEPS/MERA) — core to your QPEPS-QMERA design work",
    "B_vqe": "variational quantum eigensolvers — your central ansatz-optimization setting",
    "C_distributed": "circuit cutting / distributed quantum computing / circuit knitting",
    "D_hamiltonian": "Hamiltonian simulation and lattice models (Ising/Heisenberg)",
    "E_qml": "quantum machine learning and quantum feature maps",
    "F_mitigation": "error mitigation, measurement reduction, and barren-plateau analysis",
}

GROUP_EXPERIMENT: dict[str, str] = {
    "A_tensor_networks": "Reproduce the ansatz on a small 1D/2D lattice; compare parameter count vs energy error against an MPS baseline.",
    "B_vqe": "Run the VQE on a 2–4 qubit toy Hamiltonian; compare convergence and final energy error vs a fixed-depth baseline.",
    "C_distributed": "Apply circuit cutting to a small circuit; measure reconstruction sampling overhead vs an uncut baseline.",
    "D_hamiltonian": "Simulate the model on a 4-site lattice; compare energy error vs exact diagonalization.",
    "E_qml": "Train the feature map/kernel on a tiny synthetic dataset; compare accuracy vs a classical linear baseline.",
    "F_mitigation": "Apply the mitigation method to a noisy toy circuit; measure error reduction vs the unmitigated run.",
}

# Group weights for relevance (user prioritizes tensor networks + VQE).
GROUP_WEIGHT: dict[str, float] = {
    "A_tensor_networks": 2.0,
    "B_vqe": 2.0,
    "C_distributed": 1.2,
    "D_hamiltonian": 1.0,
    "E_qml": 0.9,
    "F_mitigation": 0.9,
}

_NOVELTY_CUES = (
    "we propose", "we introduce", "we present", "we develop", "novel", "for the first time",
    "new method", "new approach", "new algorithm", "unprecedented", "first demonstration",
)
_CONTRIB_CUES = (
    "we propose", "we introduce", "we present", "we develop", "we show", "we demonstrate",
    "we study", "we investigate", "in this paper", "this work", "we construct",
)
_CLAIM_CUES = (
    "achieve", "outperform", "reduce", "reduces", "improv", "demonstrate", "show that",
    "we find", "results show", "up to", "faster", "lower error", "higher accuracy",
    "speedup", "more accurate", "fewer parameters",
)
_HARD_CUES = (
    "fault-tolerant", "large-scale", "thousands of qubits", "hundreds of qubits", "gpu",
    "supercomputer", "real hardware", "experimental realization", "deep circuit",
    "scalable to", "industrial",
)
_EASY_CUES = (
    "toy", "small", "numerical simulation", "classical simulation", "proof of concept",
    "few qubits", "2-qubit", "4-qubit", "benchmark", "minimal", "illustrative",
)
_METHOD_CUES = (
    "ansatz", "variational", "optimizer", "gradient", "monte carlo", "tensor contraction",
    "trotter", "circuit", "kernel", "feature map", "hamiltonian", "eigensolver",
)
_BENCHMARKS = (
    "ising", "transverse field", "tfim", "heisenberg", "xxz", "hubbard", "fermi-hubbard",
    "h2", "lih", "beh2", "h2o", "n2", "mnist", "iris", "spin chain", "kitaev",
    "lattice gauge", "schwinger", "hydrogen chain",
)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _match_keyword_groups(text: str) -> tuple[list[str], list[str]]:
    """Return (matched_group_ids, matched_keywords) for the lower-cased text."""
    groups: list[str] = []
    keywords: list[str] = []
    for gid, kws in KEYWORD_GROUPS.items():
        hit = [k for k in kws if k in text]
        if hit:
            groups.append(gid)
            keywords.extend(hit)
    return groups, keywords


def _round(x: float) -> float:
    return round(max(0.0, min(5.0, x)), 1)


def score_relevance(matched_groups: list[str], categories: list[str]) -> float:
    score = sum(GROUP_WEIGHT.get(g, 0.5) for g in matched_groups)
    if "quant-ph" in [c.lower() for c in categories]:
        score += 0.5
    return _round(score)


def score_novelty(text: str) -> float:
    if any(w in text for w in ("review", "survey", "lecture notes")):
        return 1.0
    hits = sum(1 for cue in _NOVELTY_CUES if cue in text)
    return _round(1.5 + hits)


def score_difficulty(text: str) -> float:
    score = 2.5 + sum(0.7 for c in _HARD_CUES if c in text)
    score -= sum(0.5 for c in _EASY_CUES if c in text)
    return _round(score)


def decide_action(relevance: float, novelty: float, difficulty: float) -> RecommendedAction:
    if relevance < 1.0:
        return RecommendedAction.IGNORE
    if relevance < 2.5:
        return RecommendedAction.TRACK
    if relevance >= 4.0 and novelty >= 3.0 and difficulty <= 3.0:
        return RecommendedAction.EXTEND
    if relevance >= 3.0 and difficulty <= 3.5:
        return RecommendedAction.REPRODUCE
    return RecommendedAction.SUMMARIZE


def _extract_contribution(sentences: list[str]) -> str:
    low = [s.lower() for s in sentences]
    for i, s in enumerate(low):
        if any(cue in s for cue in _CONTRIB_CUES):
            return sentences[i]
    return sentences[0] if sentences else ""


def _extract_claims(sentences: list[str], limit: int = 4) -> list[str]:
    out: list[str] = []
    for s in sentences:
        if any(cue in s.lower() for cue in _CLAIM_CUES):
            out.append(s if len(s) <= 240 else s[:237] + "...")
        if len(out) >= limit:
            break
    return out


def _extract_methods(text: str, matched_keywords: list[str], limit: int = 6) -> list[str]:
    methods: list[str] = []
    seen: set[str] = set()
    for kw in matched_keywords + [c for c in _METHOD_CUES if c in text]:
        norm = kw.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            methods.append(kw if kw.isupper() else kw.title())
        if len(methods) >= limit:
            break
    return methods


def _extract_benchmarks(text: str) -> list[str]:
    found = [b for b in _BENCHMARKS if b in text]
    # De-duplicate near-synonyms while preserving order.
    return [b.title() if not b.isupper() else b for b in found]


def _deterministic_card(paper: Paper, full_text: str | None = None) -> PaperCard:
    """Generate a deterministic paper card from metadata (+ optional full text)."""
    blob = f"{paper.title}\n{paper.abstract}"
    if full_text:
        blob += "\n" + full_text[:4000]
    low = blob.lower()

    matched_groups, matched_keywords = _match_keyword_groups(low)
    sentences = _sentences(paper.abstract)

    relevance = score_relevance(matched_groups, paper.categories)
    novelty = score_novelty(low)
    difficulty = score_difficulty(low)
    action = decide_action(relevance, novelty, difficulty)

    relevance_to_user = (
        "Relevant to: " + "; ".join(GROUP_RELEVANCE[g] for g in matched_groups)
        if matched_groups
        else "No direct keyword-group match; tracked as general quantum-computing context."
    )
    possible = [GROUP_EXPERIMENT[g] for g in matched_groups][:3]

    concept_result = extract_from_paper(paper.title, paper.abstract, full_text)
    concept_terms, concept_relations = concept_result.to_card_fields()

    return PaperCard(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=paper.authors,
        published=paper.published_date,
        categories=paper.categories,
        abstract=paper.abstract,
        core_contribution=_extract_contribution(sentences),
        methods=_extract_methods(low, matched_keywords),
        claims=_extract_claims(sentences),
        datasets_or_benchmarks=_extract_benchmarks(low),
        relevance_to_user=relevance_to_user,
        possible_experiments=possible,
        matched_keyword_groups=matched_groups,
        relevance_score=relevance,
        novelty_score=novelty,
        implementation_difficulty=difficulty,
        recommended_action=action,
        generated_by="deterministic",
        concept_terms=concept_terms,
        concept_relations=concept_relations,
    )


def _as_list(value: Any, *, fallback: list[str], limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return fallback
    out = [str(v).strip() for v in value if str(v).strip()]
    return out[:limit] or fallback


def _as_score(value: Any, fallback: float) -> float:
    try:
        return _round(float(value))
    except (TypeError, ValueError):
        return fallback


def _as_action(value: Any, fallback: RecommendedAction) -> RecommendedAction:
    try:
        return RecommendedAction(str(value).strip().lower())
    except ValueError:
        return fallback


def _model_refined_card(
    card: PaperCard,
    paper: Paper,
    *,
    full_text: str | None = None,
    client: JsonModelClient | None = None,
) -> PaperCard:
    payload = {
        "paper": {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "categories": paper.categories,
            "published": paper.published_date,
        },
        "deterministic_card": card.model_dump(mode="json"),
        "retrieved_text_excerpt": (full_text or "")[:6000],
        "research_focus": [
            "tensor networks",
            "VQE",
            "MPS / PEPS / MERA / QMERA",
            "hybrid QPEPS-QMERA ansatz design",
            "distributed quantum computing",
            "circuit cutting",
            "Hamiltonian simulation",
            "quantum machine learning",
        ],
    }
    data = complete_prompt_json(
        "paper_card.md",
        payload,
        system=(
            "You are a careful quantum-computing research assistant. "
            "Return only valid JSON and do not invent evidence beyond the provided paper metadata."
        ),
        client=client,
    )

    return PaperCard(
        arxiv_id=card.arxiv_id,
        title=card.title,
        authors=card.authors,
        published=card.published,
        categories=card.categories,
        abstract=card.abstract,
        core_contribution=str(data.get("core_contribution") or card.core_contribution).strip(),
        methods=_as_list(data.get("methods"), fallback=card.methods),
        claims=_as_list(data.get("claims"), fallback=card.claims, limit=5),
        datasets_or_benchmarks=_as_list(
            data.get("datasets_or_benchmarks"),
            fallback=card.datasets_or_benchmarks,
            limit=6,
        ),
        relevance_to_user=str(data.get("relevance_to_user") or card.relevance_to_user).strip(),
        possible_experiments=_as_list(
            data.get("possible_experiments"),
            fallback=card.possible_experiments,
            limit=4,
        ),
        matched_keyword_groups=card.matched_keyword_groups,
        relevance_score=_as_score(data.get("relevance_score"), card.relevance_score),
        novelty_score=_as_score(data.get("novelty_score"), card.novelty_score),
        implementation_difficulty=_as_score(
            data.get("implementation_difficulty"),
            card.implementation_difficulty,
        ),
        recommended_action=_as_action(data.get("recommended_action"), card.recommended_action),
        generated_by="claude_model_pass",
    )


def generate_card(
    paper: Paper,
    full_text: str | None = None,
    *,
    use_model: bool | None = None,
    model_client: JsonModelClient | None = None,
) -> PaperCard:
    """Generate a paper card, optionally refining it with Claude.

    The deterministic card is always produced first and is the fallback if the
    model pass is disabled, unavailable, or returns invalid JSON.
    """
    card = _deterministic_card(paper, full_text)
    cfg = get_config()
    should_use_model = bool(model_client) or (
        cfg.enable_model_pass if use_model is None else use_model
    )
    if not should_use_model:
        return card
    try:
        return _model_refined_card(card, paper, full_text=full_text, client=model_client)
    except ModelPassError as exc:
        log.warning("paper-card model pass skipped for %s: %s", paper.arxiv_id, exc)
        return card


def render_card_markdown(card: PaperCard) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- (none detected)"

    return f"""# Paper Card — {card.title}

**arXiv:** [{card.arxiv_id}](https://arxiv.org/abs/{card.arxiv_id}) ·
**Published:** {card.published or "n/a"} ·
**Categories:** {", ".join(card.categories) or "n/a"}

**Authors:** {", ".join(card.authors) or "n/a"}

## Scores
| Relevance | Novelty | Impl. difficulty | Action |
|---|---|---|---|
| {card.relevance_score} | {card.novelty_score} | {card.implementation_difficulty} | **{card.recommended_action.value}** |

Matched keyword groups: {", ".join(card.matched_keyword_groups) or "none"}

## Core contribution
{card.core_contribution or "(not detected)"}

## Methods
{bullets(card.methods)}

## Key claims
{bullets(card.claims)}

## Datasets / benchmarks
{bullets(card.datasets_or_benchmarks)}

## Relevance to your research
{card.relevance_to_user}

## Possible experiments
{bullets(card.possible_experiments)}

## Abstract
{card.abstract}

---
*Generated deterministically by the Quantum Research Hub (no model call).*
"""


def save_card(card: PaperCard) -> Path:
    """Persist the card as JSON + Markdown under ``data/papers/cards``.

    Returns the JSON path (stored on ``papers.paper_card_path``).
    """
    cfg = get_config()
    cfg.cards_dir.mkdir(parents=True, exist_ok=True)
    json_path = cfg.cards_dir / f"{card.arxiv_id}.json"
    md_path = cfg.cards_dir / f"{card.arxiv_id}.md"
    json_path.write_text(json.dumps(card.model_dump(mode="json"), indent=2), encoding="utf-8")
    md_path.write_text(render_card_markdown(card), encoding="utf-8")
    return json_path
