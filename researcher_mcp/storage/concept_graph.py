"""SQLite-backed concept graph for the synthesis engine.

Three tables (all additive — see schema.sql):
  concepts        — canonical concept nodes
  paper_concepts  — which concepts appear in which paper (weighted)
  concept_edges   — weighted, typed directed edges between concepts

Public surface:
  update_graph_from_paper(arxiv_id, result)   — ingest one paper's extraction
  get_concept_neighbors(name, ...)             — 1-hop query
  get_concept_papers(name)                     — papers mentioning a concept
  get_top_concepts(limit, concept_type)        — global ranking
  get_concept_cluster(seeds, ...)              — BFS subgraph for visualization
  bfs_path(source, target)                     — shortest cross-concept path
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

from ..ingest.concept_extractor import CONCEPT_REGISTRY, ConceptExtractionResult
from ..logging_utils import get_logger
from .db import get_connection

log = get_logger("storage.concept_graph")


# ---------------------------------------------------------------------------
# Public: ingest
# ---------------------------------------------------------------------------

def update_graph_from_paper(
    arxiv_id: str, result: ConceptExtractionResult, *, recompute: bool = True
) -> dict[str, int]:
    """Persist one paper's extraction result into the concept graph.

    Delegates to the batched indexing writer (one connection, evidence rows with
    provenance) rather than the old per-row connection-per-write path. Edges are
    re-derived from the persisted evidence so re-indexing is idempotent.

    Returns {"concepts_added": N, "edges_added": N} for logging/back-compat.
    """
    # Imported lazily to avoid any storage<->indexing import-time coupling.
    from ..indexing.graph_store import index_extraction
    from ..indexing.writer import BatchWriter

    with BatchWriter() as writer:
        stats = index_extraction(writer, arxiv_id, result)
        if recompute:
            writer.recompute_aggregates()

    log.info(
        "concept graph updated for %s: %d concepts, %d evidence rows",
        arxiv_id, stats["concepts"], stats["evidence"],
    )
    return {"concepts_added": stats["concepts"], "edges_added": stats["evidence"]}


def get_relation_evidence(
    source: str, target: str, relation: str | None = None, limit: int = 10
) -> list[dict]:
    """Return persisted evidence sentences backing a concept relation."""
    with get_connection() as conn:
        if relation:
            rows = conn.execute(
                """SELECT arxiv_id, source, target, relation, evidence_text, section, confidence
                   FROM relation_evidence WHERE source=? AND target=? AND relation=?
                   ORDER BY confidence DESC LIMIT ?""",
                (source, target, relation, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT arxiv_id, source, target, relation, evidence_text, section, confidence
                   FROM relation_evidence WHERE source=? AND target=?
                   ORDER BY confidence DESC LIMIT ?""",
                (source, target, limit),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Public: reads
# ---------------------------------------------------------------------------

def get_concept_neighbors(
    concept_name: str,
    *,
    relation: str | None = None,
    min_weight: float = 0.0,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return edges adjacent to concept_name (both directions)."""
    with get_connection() as conn:
        params: list[Any] = [concept_name, concept_name]
        rel_clause = ""
        if relation:
            rel_clause = " AND relation = ?"
            params = [concept_name, concept_name, relation]
        params.append(min_weight)
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT source, target, relation, weight, paper_ids_json
            FROM concept_edges
            WHERE (source = ? OR target = ?) {rel_clause}
              AND weight >= ?
            ORDER BY weight DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

        return [
            {
                "source": r["source"],
                "target": r["target"],
                "neighbor": r["target"] if r["source"] == concept_name else r["source"],
                "relation": r["relation"],
                "weight": round(r["weight"], 2),
                "paper_count": len(json.loads(r["paper_ids_json"] or "[]")),
                "paper_ids": json.loads(r["paper_ids_json"] or "[]"),
            }
            for r in rows
        ]


def get_concept_papers(concept_name: str, limit: int = 15) -> list[str]:
    """arXiv IDs of papers that mention this concept, ordered by score."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT arxiv_id FROM paper_concepts WHERE concept_name=? ORDER BY score DESC LIMIT ?",
            (concept_name, limit),
        ).fetchall()
        return [r["arxiv_id"] for r in rows]


def get_top_concepts(limit: int = 40, concept_type: str | None = None) -> list[dict[str, Any]]:
    """Concepts ranked by paper_count (how many papers mention them)."""
    with get_connection() as conn:
        if concept_type:
            rows = conn.execute(
                "SELECT name, concept_type, description, paper_count FROM concepts "
                "WHERE concept_type = ? ORDER BY paper_count DESC, name ASC LIMIT ?",
                (concept_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, concept_type, description, paper_count FROM concepts "
                "ORDER BY paper_count DESC, name ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def bfs_path(source: str, target: str, max_hops: int = 4) -> list[str] | None:
    """BFS shortest path between two concept nodes; None if unreachable within max_hops."""
    if source == target:
        return [source]

    with get_connection() as conn:
        visited: set[str] = {source}
        queue: deque[list[str]] = deque([[source]])

        while queue:
            path = queue.popleft()
            if len(path) > max_hops + 1:
                return None
            current = path[-1]
            rows = conn.execute(
                "SELECT source, target FROM concept_edges WHERE source = ? OR target = ? ORDER BY weight DESC LIMIT 25",
                (current, current),
            ).fetchall()
            for row in rows:
                neighbor = row["target"] if row["source"] == current else row["source"]
                if neighbor in visited:
                    continue
                new_path = path + [neighbor]
                if neighbor == target:
                    return new_path
                visited.add(neighbor)
                queue.append(new_path)

    return None


def get_concept_cluster(
    seed_concepts: list[str],
    *,
    max_nodes: int = 60,
    min_weight: float = 0.3,
    max_hops: int = 2,
) -> dict[str, Any]:
    """BFS subgraph around seed concepts for visualization / synthesis.

    Returns {"nodes": [...], "edges": [...]} where nodes have metadata and
    edges have source/target/relation/weight.
    """
    visited: set[str] = set(seed_concepts)
    frontier = list(seed_concepts)
    all_edges: list[dict] = []
    hop = 0

    while frontier and len(visited) < max_nodes and hop < max_hops:
        next_frontier: list[str] = []
        for concept in frontier:
            neighbors = get_concept_neighbors(concept, min_weight=min_weight, limit=12)
            for n in neighbors:
                all_edges.append(n)
                nb = n["neighbor"]
                if nb not in visited:
                    visited.add(nb)
                    next_frontier.append(nb)
        frontier = next_frontier
        hop += 1

    # Deduplicate edges
    seen_edges: set[tuple[str, str, str]] = set()
    unique_edges: list[dict] = []
    for e in all_edges:
        key = (e["source"], e["target"], e["relation"])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append({
                "source": e["source"],
                "target": e["target"],
                "relation": e["relation"],
                "weight": e["weight"],
                "paper_count": e["paper_count"],
            })

    # Fetch node metadata
    with get_connection() as conn:
        nodes: list[dict] = []
        for name in visited:
            row = conn.execute(
                "SELECT name, concept_type, description, paper_count FROM concepts WHERE name=?",
                (name,),
            ).fetchone()
            if row:
                nodes.append(dict(row))
            else:
                nodes.append({"name": name, "concept_type": "unknown", "description": name, "paper_count": 0})

    return {
        "node_count": len(nodes),
        "edge_count": len(unique_edges),
        "nodes": nodes,
        "edges": unique_edges,
    }


def search_concepts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Full-text search over concept names and descriptions."""
    q = query.lower().strip()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT name, concept_type, description, paper_count FROM concepts
            WHERE lower(name) LIKE ? OR lower(description) LIKE ? OR lower(aliases_json) LIKE ?
            ORDER BY paper_count DESC, name ASC
            LIMIT ?
            """,
            (f"%{q}%", f"%{q}%", f"%{q}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_bridge_concepts(concept_a: str, concept_b: str) -> dict[str, Any]:
    """Find the shortest concept path between two concepts and enrich each hop."""
    path = bfs_path(concept_a, concept_b)
    if path is None:
        return {
            "found": False,
            "concept_a": concept_a,
            "concept_b": concept_b,
            "path": [],
            "hops": None,
            "note": "No path found within 4 hops.",
        }

    # For each consecutive pair, fetch the edge
    edge_details: list[dict] = []
    for i in range(len(path) - 1):
        edges = get_concept_neighbors(path[i], limit=50)
        for e in edges:
            if e["neighbor"] == path[i + 1]:
                edge_details.append({
                    "from": path[i],
                    "to": path[i + 1],
                    "relation": e["relation"],
                    "weight": e["weight"],
                    "shared_papers": e["paper_ids"][:5],
                })
                break
        else:
            edge_details.append({"from": path[i], "to": path[i + 1], "relation": "?", "weight": 0})

    return {
        "found": True,
        "concept_a": concept_a,
        "concept_b": concept_b,
        "path": path,
        "hops": len(path) - 1,
        "edges": edge_details,
    }
