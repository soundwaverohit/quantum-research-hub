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
# Low-level writes
# ---------------------------------------------------------------------------

def _upsert_concept(name: str, concept_type: str, description: str, aliases: list[str]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO concepts (name, concept_type, description, aliases_json, paper_count)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(name) DO UPDATE SET
              concept_type  = excluded.concept_type,
              description   = COALESCE(NULLIF(excluded.description, ''), concepts.description),
              aliases_json  = excluded.aliases_json
            """,
            (name, concept_type, description, json.dumps(aliases)),
        )


def _increment_paper_count(name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE concepts SET paper_count = paper_count + 1 WHERE name = ?", (name,)
        )


def _upsert_paper_concept(arxiv_id: str, concept_name: str, score: float) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO paper_concepts (arxiv_id, concept_name, score)
            VALUES (?, ?, ?)
            ON CONFLICT(arxiv_id, concept_name) DO UPDATE SET
              score = MAX(excluded.score, paper_concepts.score)
            """,
            (arxiv_id, concept_name, score),
        )


def _upsert_edge(source: str, target: str, relation: str, weight_delta: float, paper_id: str | None) -> None:
    # Normalize direction for symmetric relations so we don't double-count
    if relation in ("co_occurs", "compared_to") and source > target:
        source, target = target, source

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, weight, paper_ids_json FROM concept_edges WHERE source=? AND target=? AND relation=?",
            (source, target, relation),
        ).fetchone()

        if row:
            ids: list[str] = json.loads(row["paper_ids_json"] or "[]")
            if paper_id and paper_id not in ids:
                ids.append(paper_id)
            conn.execute(
                "UPDATE concept_edges SET weight = weight + ?, paper_ids_json = ? WHERE id = ?",
                (weight_delta, json.dumps(ids), row["id"]),
            )
        else:
            ids = [paper_id] if paper_id else []
            conn.execute(
                """
                INSERT INTO concept_edges (source, target, relation, weight, paper_ids_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (source, target, relation, weight_delta, json.dumps(ids)),
            )


# ---------------------------------------------------------------------------
# Public: ingest
# ---------------------------------------------------------------------------

def update_graph_from_paper(arxiv_id: str, result: ConceptExtractionResult) -> dict[str, int]:
    """Persist one paper's extraction result into the concept graph.

    Returns {"concepts_added": N, "edges_added": N} for logging.
    """
    scores = result.concept_scores()
    seen: set[str] = set()

    for canon in result.unique_concept_names():
        if canon not in CONCEPT_REGISTRY:
            continue
        meta = CONCEPT_REGISTRY[canon]
        _upsert_concept(canon, meta.type, meta.description, list(meta.aliases))
        _upsert_paper_concept(arxiv_id, canon, scores.get(canon, 0.0))
        if canon not in seen:
            seen.add(canon)
            _increment_paper_count(canon)

    edge_count = 0
    for rel in result.relations:
        if rel.source not in CONCEPT_REGISTRY or rel.target not in CONCEPT_REGISTRY:
            continue
        _upsert_edge(rel.source, rel.target, rel.relation, rel.weight, arxiv_id)
        edge_count += 1

    log.info(
        "concept graph updated for %s: %d concepts, %d relations",
        arxiv_id, len(seen), edge_count,
    )
    return {"concepts_added": len(seen), "edges_added": edge_count}


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
