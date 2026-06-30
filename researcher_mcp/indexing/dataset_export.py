"""Export the concept map as a first-principles scientific-reasoning dataset.

Four complementary supervised formats, all grounded in persisted evidence so
every sample carries provenance back to the source literature:

  triples       (source, relation, target) + the exact evidence sentence.
  chains        multi-hop reasoning traces walking the graph, evidence per hop.
  qa            grounded question/answer pairs over a concept's neighborhood.
  contrastive   pairs of papers that characterize the same concept pair
                differently — supervision for evidence-weighing / disagreement.

Each record shares one envelope::

    {
      "id", "type", "domain",
      "text":        natural-language rendering (the training target),
      "structured":  machine-readable fields,
      "provenance":  {paper_ids, arxiv_urls, evidence:[...]},
      "meta":        {confidence, relation, hops, ...}
    }

CLI::

    python -m researcher_mcp.indexing.dataset_export --format all
    python -m researcher_mcp.indexing.dataset_export --format triples --min-confidence 0.6
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from ..config import get_config
from ..ingest.concept_extractor import RELATION_PHRASE
from ..logging_utils import get_logger
from ..storage.db import get_connection

log = get_logger("indexing.dataset_export")

DOMAIN = "quantum-computing"
_TYPED = "relation != 'co_occurs'"


def _arxiv_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_id}"


def _phrase(relation: str) -> str:
    return RELATION_PHRASE.get(relation, relation.replace("_", " "))


def _concept_maps(conn) -> tuple[dict[str, str], dict[str, str]]:
    display: dict[str, str] = {}
    ctype: dict[str, str] = {}
    for r in conn.execute("SELECT name, description, concept_type FROM concepts").fetchall():
        display[r["name"]] = r["description"] or r["name"]
        ctype[r["name"]] = r["concept_type"]
    return display, ctype


def _best_evidence(conn) -> dict[tuple[str, str, str], dict]:
    """Highest-confidence evidence row per (source, target, relation)."""
    best: dict[tuple[str, str, str], dict] = {}
    rows = conn.execute(
        """
        SELECT source, target, relation, evidence_text, char_start, char_end,
               section, arxiv_id, confidence
        FROM relation_evidence ORDER BY confidence DESC
        """
    ).fetchall()
    for r in rows:
        key = (r["source"], r["target"], r["relation"])
        if key not in best:
            best[key] = dict(r)
    return best


def _write_jsonl(path: Path, records: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


# ---------------------------------------------------------------------------
# 1) Triples
# ---------------------------------------------------------------------------

def build_triples(min_confidence: float = 0.5, include_co_occurs: bool = False,
                  limit: int | None = None) -> list[dict]:
    with get_connection() as conn:
        display, ctype = _concept_maps(conn)
        clause = "" if include_co_occurs else f"WHERE {_TYPED}"
        conf_clause = ("AND" if clause else "WHERE") + " confidence >= ?"
        sql = (
            "SELECT id, arxiv_id, source, target, relation, evidence_text, "
            "char_start, char_end, section, confidence "
            f"FROM relation_evidence {clause} {conf_clause} "
            "ORDER BY confidence DESC"
        )
        params: list[Any] = [min_confidence]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()

    records: list[dict] = []
    for r in rows:
        s, t, rel = r["source"], r["target"], r["relation"]
        sd, td = display.get(s, s), display.get(t, t)
        records.append({
            "id": f"triple-{r['id']}",
            "type": "triple",
            "domain": DOMAIN,
            "text": f"{sd} {_phrase(rel)} {td}.",
            "structured": {
                "source": s, "source_type": ctype.get(s, ""),
                "relation": rel,
                "target": t, "target_type": ctype.get(t, ""),
            },
            "provenance": {
                "paper_ids": [r["arxiv_id"]],
                "arxiv_urls": [_arxiv_url(r["arxiv_id"])],
                "evidence": [{
                    "text": r["evidence_text"],
                    "char_start": r["char_start"], "char_end": r["char_end"],
                    "section": r["section"],
                }],
            },
            "meta": {"confidence": round(r["confidence"], 3), "relation": rel},
        })
    return records


# ---------------------------------------------------------------------------
# 2) Reasoning chains
# ---------------------------------------------------------------------------

def build_reasoning_chains(max_hops: int = 3, min_confidence: float = 0.5,
                           max_chains: int = 2000) -> list[dict]:
    with get_connection() as conn:
        display, ctype = _concept_maps(conn)
        evidence = _best_evidence(conn)
        edges = conn.execute(
            f"SELECT source, target, relation, weight FROM concept_edges WHERE {_TYPED}"
        ).fetchall()

    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in edges:
        # only hops that have evidence at/above threshold
        key = (e["source"], e["target"], e["relation"])
        ev = evidence.get(key)
        if ev and ev["confidence"] >= min_confidence:
            adj[e["source"]].append((e["target"], e["relation"]))

    records: list[dict] = []

    def hop_evidence(s: str, t: str, rel: str) -> dict | None:
        return evidence.get((s, t, rel))

    def emit(nodes: list[str], rels: list[str]) -> None:
        steps = []
        papers: list[str] = []
        ev_list: list[dict] = []
        confs: list[float] = []
        for i, rel in enumerate(rels):
            ev = hop_evidence(nodes[i], nodes[i + 1], rel)
            if ev is None:
                return
            steps.append({
                "from": nodes[i], "to": nodes[i + 1], "relation": rel,
                "evidence": ev["evidence_text"],
            })
            confs.append(ev["confidence"])
            if ev["arxiv_id"] not in papers:
                papers.append(ev["arxiv_id"])
            ev_list.append({
                "text": ev["evidence_text"], "section": ev["section"],
                "char_start": ev["char_start"], "char_end": ev["char_end"],
            })
        disp = [display.get(n, n) for n in nodes]
        clauses = [
            f"{disp[i]} {_phrase(rels[i])} {disp[i + 1]}"
            for i in range(len(rels))
        ]
        text = (
            "Because " + ", and ".join(clauses)
            + f", {disp[0]} is connected to {disp[-1]} through "
            + ", ".join(disp[1:-1]) + "."
        )
        records.append({
            "id": f"chain-{'_'.join(nodes)}",
            "type": "reasoning_chain",
            "domain": DOMAIN,
            "text": text,
            "structured": {"nodes": nodes, "steps": steps},
            "provenance": {
                "paper_ids": papers,
                "arxiv_urls": [_arxiv_url(p) for p in papers],
                "evidence": ev_list,
            },
            "meta": {"hops": len(rels), "min_confidence": round(min(confs), 3)},
        })

    # Enumerate 2-hop then 3-hop simple paths.
    for a in list(adj.keys()):
        for b, r1 in adj[a]:
            for c, r2 in adj.get(b, []):
                if c == a or c == b:
                    continue
                emit([a, b, c], [r1, r2])
                if len(records) >= max_chains:
                    return records
                if max_hops >= 3:
                    for d, r3 in adj.get(c, []):
                        if d in (a, b, c):
                            continue
                        emit([a, b, c, d], [r1, r2, r3])
                        if len(records) >= max_chains:
                            return records
    return records


# ---------------------------------------------------------------------------
# 3) Grounded QA pairs
# ---------------------------------------------------------------------------

def build_qa_pairs(max_pairs: int = 2000, min_confidence: float = 0.5) -> list[dict]:
    with get_connection() as conn:
        display, ctype = _concept_maps(conn)
        evidence = _best_evidence(conn)
        edges = conn.execute(
            f"SELECT source, target, relation, weight FROM concept_edges WHERE {_TYPED} "
            "ORDER BY weight DESC"
        ).fetchall()

    by_source: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        by_source[e["source"]].append(dict(e))

    records: list[dict] = []

    # Template A: neighborhood summary per concept.
    for concept, outs in by_source.items():
        cd = display.get(concept, concept)
        lines: list[str] = []
        papers: list[str] = []
        ev_list: list[dict] = []
        for e in outs[:6]:
            key = (e["source"], e["target"], e["relation"])
            ev = evidence.get(key)
            if not ev or ev["confidence"] < min_confidence:
                continue
            td = display.get(e["target"], e["target"])
            lines.append(f"- {cd} {_phrase(e['relation'])} {td} (e.g. arXiv:{ev['arxiv_id']}).")
            if ev["arxiv_id"] not in papers:
                papers.append(ev["arxiv_id"])
            ev_list.append({"text": ev["evidence_text"], "section": ev["section"]})
        if not lines:
            continue
        records.append({
            "id": f"qa-neighbors-{concept}",
            "type": "qa",
            "domain": DOMAIN,
            "text": (
                f"Q: According to the indexed literature, how does {cd} relate to "
                f"other concepts?\nA:\n" + "\n".join(lines)
            ),
            "structured": {
                "question": f"How does {cd} relate to other concepts in the literature?",
                "answer_points": lines,
                "concept": concept,
            },
            "provenance": {
                "paper_ids": papers,
                "arxiv_urls": [_arxiv_url(p) for p in papers],
                "evidence": ev_list,
            },
            "meta": {"template": "neighborhood", "relation_count": len(lines)},
        })
        if len(records) >= max_pairs:
            return records

    # Template B: targeted "what does X improve on?" questions.
    for concept, outs in by_source.items():
        improves = [e for e in outs if e["relation"] == "improves_on"]
        if not improves:
            continue
        cd = display.get(concept, concept)
        papers, ev_list, targets = [], [], []
        for e in improves[:4]:
            ev = evidence.get((e["source"], e["target"], e["relation"]))
            if not ev:
                continue
            targets.append(display.get(e["target"], e["target"]))
            if ev["arxiv_id"] not in papers:
                papers.append(ev["arxiv_id"])
            ev_list.append({"text": ev["evidence_text"], "section": ev["section"]})
        if not targets:
            continue
        records.append({
            "id": f"qa-improves-{concept}",
            "type": "qa",
            "domain": DOMAIN,
            "text": (
                f"Q: What does {cd} improve on, and on what basis?\n"
                f"A: {cd} is reported to improve on {', '.join(targets)}, "
                f"based on {len(papers)} paper(s) in the index."
            ),
            "structured": {
                "question": f"What does {cd} improve on?",
                "targets": targets, "concept": concept,
            },
            "provenance": {
                "paper_ids": papers,
                "arxiv_urls": [_arxiv_url(p) for p in papers],
                "evidence": ev_list,
            },
            "meta": {"template": "improves_on"},
        })
        if len(records) >= max_pairs:
            return records
    return records


# ---------------------------------------------------------------------------
# 4) Contrastive claim pairs
# ---------------------------------------------------------------------------

def build_contrastive(max_pairs: int = 1000) -> list[dict]:
    with get_connection() as conn:
        display, _ = _concept_maps(conn)
        rows = conn.execute(
            """
            SELECT source, target, relation, evidence_text, section, arxiv_id, confidence
            FROM relation_evidence ORDER BY confidence DESC
            """
        ).fetchall()

    # Group by unordered concept pair -> per-relation representative claims.
    pairs: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for r in rows:
        a, b = r["source"], r["target"]
        key = (a, b) if a <= b else (b, a)
        rel = r["relation"]
        if rel not in pairs[key]:  # first (highest-confidence) wins
            pairs[key][rel] = dict(r)

    records: list[dict] = []
    for (a, b), rel_map in pairs.items():
        if len(rel_map) < 2:
            continue
        # Need at least two *different* characterizations from distinct papers.
        positions = list(rel_map.values())
        paper_ids = {p["arxiv_id"] for p in positions}
        if len(paper_ids) < 2:
            continue
        ad, bd = display.get(a, a), display.get(b, b)
        pos_struct = [{
            "relation": p["relation"], "paper_id": p["arxiv_id"],
            "evidence": p["evidence_text"], "confidence": round(p["confidence"], 3),
        } for p in positions]
        text_parts = [
            f"arXiv:{p['arxiv_id']} characterizes the relationship between {ad} and "
            f"{bd} as '{_phrase(p['relation'])}' (\"{p['evidence_text'][:160]}\")"
            for p in positions
        ]
        records.append({
            "id": f"contrast-{a}-{b}",
            "type": "contrastive",
            "domain": DOMAIN,
            "text": (
                "Different papers characterize the same relationship differently. "
                + "; while ".join(text_parts)
                + ". Weigh the evidence to decide which characterization the data supports."
            ),
            "structured": {"concept_a": a, "concept_b": b, "positions": pos_struct},
            "provenance": {
                "paper_ids": sorted(paper_ids),
                "arxiv_urls": [_arxiv_url(p) for p in sorted(paper_ids)],
                "evidence": [{"text": p["evidence_text"], "section": p["section"]} for p in positions],
            },
            "meta": {"relation_types": sorted(rel_map.keys())},
        })
        if len(records) >= max_pairs:
            break
    return records


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_BUILDERS = {
    "triples": build_triples,
    "chains": build_reasoning_chains,
    "qa": build_qa_pairs,
    "contrastive": build_contrastive,
}


def export_dataset(
    formats: list[str] | None = None,
    *,
    out_dir: Path | None = None,
    min_confidence: float = 0.5,
) -> dict:
    """Build the requested dataset formats and write them as JSONL.

    Returns {"out_dir", "files": {format: {path, count}}, "total"}.
    """
    cfg = get_config()
    out_dir = out_dir or cfg.datasets_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = formats or list(_BUILDERS)

    files: dict[str, dict] = {}
    total = 0
    for fmt in formats:
        if fmt not in _BUILDERS:
            continue
        if fmt == "triples":
            records = build_triples(min_confidence=min_confidence)
        elif fmt == "chains":
            records = build_reasoning_chains(min_confidence=min_confidence)
        elif fmt == "qa":
            records = build_qa_pairs(min_confidence=min_confidence)
        else:
            records = build_contrastive()
        path = out_dir / f"{fmt}.jsonl"
        n = _write_jsonl(path, records)
        files[fmt] = {"path": str(path), "count": n}
        total += n
        log.info("exported %d %s records -> %s", n, fmt, path)

    manifest = {
        "domain": DOMAIN,
        "min_confidence": min_confidence,
        "files": files,
        "total_records": total,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"out_dir": str(out_dir), "files": files, "total": total}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="researcher_mcp.indexing.dataset_export")
    parser.add_argument(
        "--format", default="all",
        help="comma-separated: triples,chains,qa,contrastive (or 'all')",
    )
    parser.add_argument("--out", default=None, help="output directory")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    args = parser.parse_args(argv)

    formats = list(_BUILDERS) if args.format == "all" else [
        f.strip() for f in args.format.split(",") if f.strip()
    ]
    out = export_dataset(
        formats,
        out_dir=Path(args.out) if args.out else None,
        min_confidence=args.min_confidence,
    )
    print(f"Exported {out['total']} records to {out['out_dir']}")
    for fmt, info in out["files"].items():
        print(f"  {fmt:14} {info['count']:6}  -> {info['path']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
