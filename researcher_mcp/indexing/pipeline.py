"""Literature indexing pipeline.

Streams papers through concept extraction + domain-general term mining and
persists everything into the concept-map database via a single batched writer.

CLI::

    python -m researcher_mcp.indexing.pipeline build [--reset] [--limit N]
    python -m researcher_mcp.indexing.pipeline stats
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from ..ingest.concept_extractor import ALIAS_TO_CANONICAL, extract_from_paper
from ..logging_utils import get_logger
from ..storage import repository as repo
from ..storage.db import get_connection
from ..storage.models import Paper
from . import graph_store
from .term_miner import MinedTerm, is_promotable, mine_document
from .writer import BatchWriter

log = get_logger("indexing.pipeline")

_INDEX_TABLES = (
    "relation_evidence", "paper_concepts", "concept_edges", "mined_terms",
)


def _read_full_text(paper: Paper) -> str | None:
    if not paper.parsed_text_path:
        return None
    p = Path(paper.parsed_text_path)
    if p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None
    return None


def _seed_registered() -> bool:
    with get_connection() as conn:
        try:
            row = conn.execute("SELECT 1 FROM concepts WHERE source='seed' LIMIT 1").fetchone()
        except Exception:  # noqa: BLE001 - table/column may not exist pre-migration
            return False
        return row is not None


def index_papers(
    papers: Iterable[Paper],
    *,
    batch_size: int = 500,
    mine: bool = True,
    promote_min_docs: int = 3,
    register_seed: bool = True,
    rebuild_aggregates: bool = True,
) -> dict[str, int]:
    """Index a stream of papers into the concept-map database.

    Returns a stats dict (papers, concepts/evidence buffered, mined, promoted).
    """
    corpus_terms: dict[str, MinedTerm] = {}
    doc_freq: Counter[str] = Counter()
    term_papers: dict[str, list[tuple[str, int]]] = defaultdict(list)

    papers_seen = 0
    total_evidence = 0

    with BatchWriter(batch_size=batch_size) as writer:
        if register_seed:
            graph_store.register_seed_ontology(writer)

        for paper in papers:
            papers_seen += 1
            full_text = _read_full_text(paper)
            result = extract_from_paper(paper.title, paper.abstract, full_text)
            section = "body" if full_text else "abstract"
            stats = graph_store.index_extraction(writer, paper.arxiv_id, result, section=section)
            total_evidence += stats["evidence"]

            if mine:
                blob = f"{paper.title}. {paper.abstract}"
                if full_text:
                    blob += " " + full_text[:2000]
                for term_key, mined in mine_document(blob).items():
                    # Skip candidates already covered by the curated seed ontology.
                    if term_key in ALIAS_TO_CANONICAL:
                        continue
                    if term_key in corpus_terms:
                        corpus_terms[term_key].merge(mined)
                    else:
                        corpus_terms[term_key] = mined
                    doc_freq[term_key] += 1
                    term_papers[term_key].append((paper.arxiv_id, mined.count))

        # Decide mined-term promotions across the whole corpus.
        promoted = 0
        for term_key, mined in corpus_terms.items():
            df = doc_freq[term_key]
            if is_promotable(mined, df, min_docs=promote_min_docs):
                concept_name = graph_store.promote_mined_concept(writer, mined, df)
                for arxiv_id, count in term_papers[term_key]:
                    graph_store.record_mined_paper_concept(writer, arxiv_id, concept_name, count)
                promoted += 1
            else:
                graph_store.record_mined_term(writer, mined, df)

        if rebuild_aggregates:
            writer.recompute_aggregates()
            writer.rebuild_fts()

    log.info(
        "indexed %d papers: %d evidence rows, %d candidate terms, %d promoted",
        papers_seen, total_evidence, len(corpus_terms), promoted,
    )
    return {
        "papers": papers_seen,
        "evidence": total_evidence,
        "candidate_terms": len(corpus_terms),
        "promoted_concepts": promoted,
        **{f"written_{k}": v for k, v in writer.written.items()},
    }


def index_single_paper(paper: Paper) -> dict[str, int]:
    """Index one paper (live ingest path). Registers seed once, lazily."""
    return index_papers(
        [paper],
        mine=True,
        register_seed=not _seed_registered(),
        rebuild_aggregates=True,
    )


def _reset_index() -> None:
    with get_connection() as conn:
        for table in _INDEX_TABLES:
            try:
                conn.execute(f"DELETE FROM {table}")
            except Exception:  # noqa: BLE001
                pass
        # Keep seed concepts; drop mined ones so a rebuild re-derives them.
        try:
            conn.execute("DELETE FROM concepts WHERE source='mined'")
            conn.execute("DELETE FROM concept_aliases WHERE source='mined'")
            conn.execute("UPDATE concepts SET paper_count=0")
        except Exception:  # noqa: BLE001
            pass


def rebuild_index(*, reset: bool = True, limit: int | None = None) -> dict[str, int]:
    """Rebuild the whole concept map from every paper in the DB."""
    if reset:
        _reset_index()
    papers = repo.list_papers(limit=limit or 100000, order_by="created_at ASC")
    return index_papers(papers)


def get_index_stats() -> dict:
    """Headline counts describing the current concept-map index."""
    with get_connection() as conn:
        def scalar(sql: str) -> int:
            try:
                return int(conn.execute(sql).fetchone()[0])
            except Exception:  # noqa: BLE001
                return 0

        rel_rows = []
        try:
            rel_rows = conn.execute(
                "SELECT relation, COUNT(*) c FROM concept_edges GROUP BY relation ORDER BY c DESC"
            ).fetchall()
        except Exception:  # noqa: BLE001
            pass

        type_rows = []
        try:
            type_rows = conn.execute(
                "SELECT concept_type, COUNT(*) c FROM concepts GROUP BY concept_type ORDER BY c DESC"
            ).fetchall()
        except Exception:  # noqa: BLE001
            pass

        return {
            "papers": scalar("SELECT COUNT(*) FROM papers"),
            "concepts_total": scalar("SELECT COUNT(*) FROM concepts"),
            "concepts_seed": scalar("SELECT COUNT(*) FROM concepts WHERE source='seed'"),
            "concepts_mined": scalar("SELECT COUNT(*) FROM concepts WHERE source='mined'"),
            "concept_aliases": scalar("SELECT COUNT(*) FROM concept_aliases"),
            "paper_concept_links": scalar("SELECT COUNT(*) FROM paper_concepts"),
            "edges": scalar("SELECT COUNT(*) FROM concept_edges"),
            "evidence_rows": scalar("SELECT COUNT(*) FROM relation_evidence"),
            "mined_terms_total": scalar("SELECT COUNT(*) FROM mined_terms"),
            "edges_by_relation": {r["relation"]: r["c"] for r in rel_rows},
            "concepts_by_type": {r["concept_type"]: r["c"] for r in type_rows},
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="researcher_mcp.indexing.pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    bp = sub.add_parser("build", help="(re)build the concept map from stored papers")
    bp.add_argument("--reset", action="store_true", help="clear the index before building")
    bp.add_argument("--limit", type=int, default=None, help="cap number of papers")
    sub.add_parser("stats", help="print concept-map index statistics")

    args = parser.parse_args(argv)
    if args.cmd == "build":
        stats = rebuild_index(reset=args.reset, limit=args.limit)
        print("Index build complete:")
        for k, v in stats.items():
            print(f"  {k:24} {v}")
    elif args.cmd == "stats":
        stats = get_index_stats()
        print("Concept-map index:")
        for k, v in stats.items():
            print(f"  {k:24} {v}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
