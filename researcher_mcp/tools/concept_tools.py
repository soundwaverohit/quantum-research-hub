"""MCP tool implementations for the concept graph / synthesis engine.

Tools:
  search_concepts      — find concept nodes by keyword
  get_concept_graph    — BFS subgraph around a set of seed concepts
  get_bridge_concepts  — shortest path between two concept nodes
"""

from __future__ import annotations

from ..storage.concept_graph import (
    get_bridge_concepts as _bridge,
    get_concept_cluster,
    get_concept_neighbors,
    get_concept_papers,
    get_top_concepts,
    search_concepts as _search,
)


def search_concepts(query: str, concept_type: str | None = None, limit: int = 20) -> dict:
    """Search the concept graph for nodes matching a keyword.

    Args:
        query: keyword to match against concept name, description, or aliases.
        concept_type: optional filter — one of method, ansatz, problem, model,
            math_object, benchmark, field, hardware.
        limit: max results.

    Returns dict with {"count", "concepts": [{name, concept_type, description, paper_count}]}.
    """
    results = _search(query, limit=limit * 2)  # over-fetch then filter
    if concept_type:
        results = [r for r in results if r.get("concept_type") == concept_type]
    results = results[:limit]
    return {"count": len(results), "concepts": results}


def get_concept_graph(
    seed_concepts: list[str],
    max_nodes: int = 50,
    min_weight: float = 0.3,
    max_hops: int = 2,
) -> dict:
    """Return a BFS subgraph rooted at seed_concepts for synthesis / visualization.

    Args:
        seed_concepts: list of canonical concept names (keys in CONCEPT_REGISTRY).
        max_nodes: cap on total nodes returned.
        min_weight: edges below this weight are excluded.
        max_hops: BFS depth from seeds.

    Returns {"node_count", "edge_count", "nodes": [...], "edges": [...]}.
    Each node: {name, concept_type, description, paper_count}.
    Each edge: {source, target, relation, weight, paper_count}.
    """
    if not seed_concepts:
        return {"node_count": 0, "edge_count": 0, "nodes": [], "edges": []}
    return get_concept_cluster(
        seed_concepts,
        max_nodes=max_nodes,
        min_weight=min_weight,
        max_hops=max_hops,
    )


def get_bridge_concepts(concept_a: str, concept_b: str) -> dict:
    """Find the shortest concept-graph path bridging two concepts.

    Useful for synthesizing connections between distant research areas.

    Args:
        concept_a: canonical name of the first concept.
        concept_b: canonical name of the second concept.

    Returns {"found", "path": [list of concept names], "hops", "edges": [{from, to, relation, shared_papers}]}.
    """
    return _bridge(concept_a, concept_b)


def get_top_concept_list(limit: int = 30, concept_type: str | None = None) -> dict:
    """Return the most paper-cited concepts, optionally filtered by type.

    Args:
        limit: max results.
        concept_type: optional filter.

    Returns {"count", "concepts": [{name, concept_type, description, paper_count}]}.
    """
    concepts = get_top_concepts(limit=limit, concept_type=concept_type or None)
    return {"count": len(concepts), "concepts": concepts}


def get_concept_neighborhood(concept_name: str, relation: str | None = None, min_weight: float = 0.0) -> dict:
    """Return 1-hop neighbors of a concept, with per-edge paper evidence.

    Args:
        concept_name: canonical concept key.
        relation: optional relation filter (e.g. 'improves_on', 'applies_to').
        min_weight: minimum edge weight.

    Returns {"concept", "neighbor_count", "neighbors": [{neighbor, relation, weight, paper_count, paper_ids}]}.
    """
    neighbors = get_concept_neighbors(
        concept_name,
        relation=relation or None,
        min_weight=min_weight,
        limit=40,
    )
    papers = get_concept_papers(concept_name, limit=10)
    return {
        "concept": concept_name,
        "papers": papers,
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }
