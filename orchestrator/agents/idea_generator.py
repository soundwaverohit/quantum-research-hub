"""Idea Generator Agent — turns ranked paper clusters into small testable ideas.

Every idea cites at least one source paper and is framed so it can be tested by
the runnable TFIM-VQE experiment template. Ideas are deliberately small and
honest (no novelty claims), and respect the per-day idea cap.
"""

from __future__ import annotations

from typing import Any

from researcher_mcp.config import KEYWORD_GROUPS, get_config
from researcher_mcp.model_pass import ModelPassError, complete_prompt_json
from researcher_mcp.tools import idea_tools, paper_tools
from researcher_mcp.tools.budget_tools import EVENT_CLAUDE_PASS, EVENT_IDEA_CREATED

from .base import Agent

# Deterministic idea seeds per keyword group. Each is intentionally small and
# maps onto the TFIM-VQE benchmark harness (a controlled proxy for harder
# techniques in groups C/E/F).
IDEA_SEEDS: dict[str, dict] = {
    "A_tensor_networks": {
        "title": "Parameter efficiency of a tensor-network-structured ansatz on a small TFIM",
        "hypothesis": "A tensor-network-structured entangling pattern reaches lower energy error than a generic hardware-efficient ansatz at equal parameter count on a 3-site TFIM.",
        "why": "Tensor-network entanglement structure matches TFIM locality, so fewer parameters should suffice.",
        "smallest": "VQE on a 3-site TFIM (J=h=1); compare structured vs generic ansatz at equal parameter count; energy error vs exact.",
        "failure": ["barren plateau at higher depth", "structured ansatz underparameterized", "optimizer trapped in local minima"],
        "novelty": 3.0, "feasibility": 4.5,
    },
    "B_vqe": {
        "title": "Ansatz depth vs VQE convergence on the TFIM",
        "hypothesis": "Increasing ansatz depth lowers VQE energy error on the small TFIM, with diminishing returns past a few layers.",
        "why": "More layers add expressivity but also more parameters to optimize and more barren-plateau risk.",
        "smallest": "Sweep ansatz_layers in {1,2,3} on a 3-site TFIM VQE; record energy error and parameter count.",
        "failure": ["overfitting to one seed", "vanishing gradients at depth", "no improvement past 2 layers"],
        "novelty": 2.5, "feasibility": 4.8,
    },
    "C_distributed": {
        "title": "Circuit-locality proxy: does a chain-entangled ansatz suffice for the TFIM?",
        "hypothesis": "A nearest-neighbour (cuttable) entangling chain reaches near-exact TFIM energy, suggesting limited need for long-range gates.",
        "why": "If local entanglement suffices, the circuit is more amenable to cutting/knitting.",
        "smallest": "Run the TFIM VQE with the nearest-neighbour CX chain ansatz; check energy error vs exact as a locality proxy.",
        "failure": ["locality insufficient near criticality", "proxy too coarse for real circuit cutting"],
        "novelty": 2.5, "feasibility": 3.5,
    },
    "D_hamiltonian": {
        "title": "Energy-error sensitivity of a fixed ansatz across TFIM field strengths",
        "hypothesis": "A fixed-depth ansatz's energy error peaks near the TFIM critical point (h≈J).",
        "why": "Correlation length grows near criticality, stressing a fixed-depth ansatz.",
        "smallest": "Run the TFIM VQE at h in {0.5, 1.0, 2.0} with fixed depth; compare energy error.",
        "failure": ["grid too coarse to see the peak", "optimizer variance masks the trend"],
        "novelty": 2.5, "feasibility": 4.3,
    },
    "E_qml": {
        "title": "Shallow-ansatz expressivity as a proxy for quantum feature maps",
        "hypothesis": "A shallow Ry+CX ansatz already captures most of the TFIM ground-state structure, bounding the benefit of richer feature maps.",
        "why": "Expressivity gains may saturate quickly on small systems.",
        "smallest": "Compare 1- vs 2-layer ansatz energy error on the 3-site TFIM as an expressivity proxy.",
        "failure": ["proxy weakly related to QML feature maps", "small-system effects dominate"],
        "novelty": 2.0, "feasibility": 3.8,
    },
    "F_mitigation": {
        "title": "Baseline sensitivity of reported VQE energy error",
        "hypothesis": "Reported VQE energy error is dominated by the baseline/seed choice on small TFIM instances.",
        "why": "Without a fixed baseline and seeds, 'improvements' can be noise — a mitigation/repro check.",
        "smallest": "Re-run the TFIM VQE across several seeds; report seed-stability std vs the headline energy error.",
        "failure": ["too few seeds", "baseline definition contested"],
        "novelty": 2.0, "feasibility": 4.5,
    },
}


class IdeaGeneratorAgent(Agent):
    name = "idea-generator"

    def _cluster(self) -> dict[str, list]:
        ctx = self.ctx
        clusters: dict[str, list] = {g: [] for g in KEYWORD_GROUPS}
        ranked = getattr(ctx, "promote", None) or ctx.ranked
        for p in ranked:
            card = paper_tools.get_paper_card(p.arxiv_id)
            for g in card.get("matched_keyword_groups", []):
                clusters[g].append(p)
        return {g: ps for g, ps in clusters.items() if ps}

    @staticmethod
    def _score(value: Any, fallback: float) -> float:
        try:
            return round(max(0.0, min(5.0, float(value))), 1)
        except (TypeError, ValueError):
            return fallback

    def _model_ideas(self, clusters: dict[str, list]) -> list[dict[str, Any]]:
        ctx = self.ctx
        cfg = get_config()
        remaining = ctx.budget.remaining(EVENT_IDEA_CREATED)
        max_ideas = min(4, remaining if remaining is not None else 4)
        if not cfg.enable_model_pass or max_ideas <= 0 or not ctx.budget.can(EVENT_CLAUDE_PASS):
            return []

        cards: list[dict[str, Any]] = []
        allowed_sources: set[str] = set()
        for group in KEYWORD_GROUPS:
            for paper in clusters.get(group, [])[:3]:
                allowed_sources.add(paper.arxiv_id)
                card = paper_tools.get_paper_card(paper.arxiv_id)
                if not card.get("error"):
                    cards.append({
                        "keyword_group": group,
                        "arxiv_id": paper.arxiv_id,
                        "title": paper.title,
                        "card": card,
                    })
                if len(cards) >= 10:
                    break
            if len(cards) >= 10:
                break

        if not cards:
            return []

        payload = {
            "max_ideas": max_ideas,
            "paper_cards": cards,
            "research_focus": [
                "hybrid QPEPS-QMERA ansatz design",
                "tensor-network-structured quantum ansatzes",
                "VQE benchmark reproducibility",
                "small CPU-only experiments with baselines",
            ],
            "constraints": {
                "must_cite_source_arxiv_ids_from_input": True,
                "must_have_smallest_experiment": True,
                "must_have_baseline": True,
                "must_have_metric": True,
                "avoid_novelty_claims_without_evidence": True,
            },
        }

        try:
            data = complete_prompt_json(
                "idea_generation.md",
                payload,
                system=(
                    "You are a skeptical quantum-computing research planner. "
                    "Generate only small, testable ideas grounded in the provided paper cards."
                ),
            )
        except ModelPassError as exc:
            self.log_event("ideate_model", "model pass", f"skipped: {exc}")
            return []

        ctx.budget.record(EVENT_CLAUDE_PASS, notes="idea_generation")
        raw_ideas = data.get("ideas") or data.get("items") or []
        if not isinstance(raw_ideas, list):
            return []

        ideas: list[dict[str, Any]] = []
        for item in raw_ideas:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            hypothesis = str(item.get("hypothesis") or "").strip()
            sources = [
                str(s).strip()
                for s in item.get("source_arxiv_ids", [])
                if str(s).strip() in allowed_sources
            ]
            if not title or not hypothesis or not sources:
                continue
            failure_modes = item.get("failure_modes", [])
            if not isinstance(failure_modes, list):
                failure_modes = []
            ideas.append({
                "title": title,
                "hypothesis": hypothesis,
                "source_arxiv_ids": sources[:3],
                "observation": str(item.get("observation") or "").strip(),
                "why_it_might_work": str(item.get("why_it_might_work") or "").strip(),
                "smallest_experiment": str(item.get("smallest_experiment") or "").strip(),
                "baseline": str(item.get("baseline") or "").strip(),
                "metric": str(item.get("metric") or "").strip(),
                "failure_modes": [str(m).strip() for m in failure_modes if str(m).strip()][:5],
                "expected_runtime": str(item.get("expected_runtime") or "< 1 minute (CPU)").strip(),
                "novelty_score": self._score(item.get("novelty_score"), 2.5),
                "feasibility_score": self._score(item.get("feasibility_score"), 3.5),
            })
            if len(ideas) >= max_ideas:
                break

        self.log_event(
            "ideate_model",
            f"{len(cards)} card(s)",
            f"Claude proposed {len(ideas)} usable idea(s)",
        )
        return ideas

    def run(self) -> dict:
        ctx = self.ctx
        clusters = self._cluster()
        created: list[str] = []

        model_ideas = self._model_ideas(clusters)
        if model_ideas:
            for idea in model_ideas:
                if not ctx.budget.can(EVENT_IDEA_CREATED):
                    break
                res = idea_tools.create_idea(**idea)
                if res.get("error"):
                    self.log_event("ideate", "claude", f"rejected: {res['error']}", status="error")
                    continue
                created.append(res["id"])
                ctx.budget.record(EVENT_IDEA_CREATED, notes=res["id"])
                self.log_event(
                    "ideate",
                    f"claude sources {idea['source_arxiv_ids']}",
                    f"idea {res['id']}: {idea['title']}",
                    artifact_path=res.get("idea_card_path"),
                )
            ctx.idea_ids = created
            return {
                "ideas_created": len(created),
                "clusters": list(clusters.keys()),
                "generated_by": "claude_model_pass",
            }

        # Generate ideas in keyword-group priority order (A..F).
        for group in KEYWORD_GROUPS:
            if group not in clusters:
                continue
            if not ctx.budget.can(EVENT_IDEA_CREATED):
                self.log_event("ideate", "budget cap", "idea cap reached; stopping ideation")
                break
            seed = IDEA_SEEDS[group]
            top = clusters[group][0]
            sources = [p.arxiv_id for p in clusters[group][:2]]
            res = idea_tools.create_idea(
                title=seed["title"],
                hypothesis=seed["hypothesis"],
                source_arxiv_ids=sources,
                observation=f"Suggested by '{top.title}' and {len(clusters[group])} related paper(s) in group {group}.",
                why_it_might_work=seed["why"],
                smallest_experiment=seed["smallest"],
                baseline="Untrained ansatz (best of random parameter sets); equal-parameter generic ansatz.",
                metric="energy_error vs exact diagonalization; improvement over baseline.",
                failure_modes=seed["failure"],
                expected_runtime="< 1 minute (CPU)",
                novelty_score=seed["novelty"],
                feasibility_score=seed["feasibility"],
            )
            if res.get("error"):
                self.log_event("ideate", group, f"rejected: {res['error']}", status="error")
                continue
            created.append(res["id"])
            ctx.budget.record(EVENT_IDEA_CREATED, notes=res["id"])
            self.log_event(
                "ideate", f"group {group} sources {sources}",
                f"idea {res['id']}: {seed['title']}",
                artifact_path=res.get("idea_card_path"),
            )

        ctx.idea_ids = created
        return {"ideas_created": len(created), "clusters": list(clusters.keys())}
