"""BatchWriter — the efficient write path for the indexing database.

The original concept-graph writer opened a brand-new SQLite connection (plus a
``PRAGMA`` and a commit) for *every* row. Ingesting one paper fired dozens of
connect/commit/close cycles; a training-scale corpus would be dominated by that
overhead.

``BatchWriter`` instead:
  * holds ONE connection for the lifetime of an ingest batch,
  * applies bulk-load PRAGMAs (WAL, ``synchronous=NORMAL``, in-memory temp),
  * buffers rows per logical table and flushes them with ``executemany`` in a
    fixed dependency order (so foreign keys stay satisfied),
  * derives the ``concept_edges`` aggregate as a pure function of the persisted
    evidence, which makes re-indexing idempotent.

Typical use::

    with BatchWriter() as w:
        for paper in papers:
            graph_store.index_extraction(w, paper.arxiv_id, result)
        w.recompute_aggregates()
        w.rebuild_fts()
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..logging_utils import get_logger
from ..storage.db import connect

log = get_logger("indexing.writer")

# Flush order respects foreign keys: concepts before anything that references a
# concept name; papers already exist before paper_concepts is written.
_FLUSH_ORDER = (
    "concepts",
    "concept_aliases",
    "paper_concepts",
    "relation_evidence",
    "mined_terms",
)

_SQL = {
    "concepts": """
        INSERT INTO concepts (name, concept_type, description, aliases_json, paper_count, source, salience)
        VALUES (?, ?, ?, ?, 0, ?, 0)
        ON CONFLICT(name) DO UPDATE SET
          concept_type = excluded.concept_type,
          description  = COALESCE(NULLIF(excluded.description, ''), concepts.description),
          aliases_json = excluded.aliases_json,
          -- once a concept is part of the curated seed it stays 'seed'
          source       = CASE WHEN concepts.source = 'seed' THEN 'seed' ELSE excluded.source END
    """,
    "concept_aliases": """
        INSERT INTO concept_aliases (alias, concept_name, source)
        VALUES (?, ?, ?)
        ON CONFLICT(alias) DO UPDATE SET concept_name = excluded.concept_name
    """,
    "paper_concepts": """
        INSERT INTO paper_concepts (arxiv_id, concept_name, score, mention_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(arxiv_id, concept_name) DO UPDATE SET
          score         = MAX(excluded.score, paper_concepts.score),
          mention_count = MAX(excluded.mention_count, paper_concepts.mention_count)
    """,
    "relation_evidence": """
        INSERT OR IGNORE INTO relation_evidence
          (arxiv_id, source, target, relation, evidence_text, char_start, char_end, section, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    "mined_terms": """
        INSERT INTO mined_terms
          (term, display, acronym, inferred_type, frequency, doc_frequency, salience)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(term) DO UPDATE SET
          display       = excluded.display,
          acronym       = COALESCE(NULLIF(excluded.acronym, ''), mined_terms.acronym),
          inferred_type = COALESCE(NULLIF(excluded.inferred_type, ''), mined_terms.inferred_type),
          frequency     = mined_terms.frequency + excluded.frequency,
          doc_frequency = mined_terms.doc_frequency + excluded.doc_frequency,
          salience      = excluded.salience,
          updated_at    = CURRENT_TIMESTAMP
    """,
}

# Relations whose direction is not meaningful; normalize so grouping merges them.
_SYMMETRIC = frozenset({"co_occurs", "compared_to"})


class BatchWriter:
    def __init__(self, db_path: Path | None = None, *, batch_size: int = 500) -> None:
        self.conn = connect(db_path)
        # Bulk-load tuning. WAL + NORMAL is durable enough for a local index and
        # an order of magnitude faster than the default fsync-per-commit.
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self.conn.execute("PRAGMA temp_store = MEMORY;")
        self.conn.execute("PRAGMA cache_size = -16000;")  # ~16 MB page cache
        self.batch_size = batch_size
        self._buffers: dict[str, list[tuple]] = defaultdict(list)
        self._counts: dict[str, int] = defaultdict(int)

    # -- buffering -----------------------------------------------------------
    def _add(self, table: str, params: tuple) -> None:
        buf = self._buffers[table]
        buf.append(params)
        if len(buf) >= self.batch_size:
            self._flush_table(table)

    def add_concept(self, name: str, concept_type: str, description: str,
                    aliases: list[str], source: str = "seed") -> None:
        import json
        self._add("concepts", (name, concept_type, description, json.dumps(aliases), source))

    def add_alias(self, alias: str, concept_name: str, source: str = "seed") -> None:
        self._add("concept_aliases", (alias.lower(), concept_name, source))

    def add_paper_concept(self, arxiv_id: str, concept_name: str,
                          score: float, mention_count: int) -> None:
        self._add("paper_concepts", (arxiv_id, concept_name, score, mention_count))

    def add_evidence(self, arxiv_id: str, source: str, target: str, relation: str,
                     evidence_text: str, char_start: int, char_end: int,
                     section: str, confidence: float) -> None:
        if relation in _SYMMETRIC and source > target:
            source, target = target, source
        self._add("relation_evidence", (
            arxiv_id, source, target, relation,
            evidence_text, char_start, char_end, section, confidence,
        ))

    def add_mined_term(self, term: str, display: str, acronym: str, inferred_type: str,
                       frequency: int, doc_frequency: int, salience: float) -> None:
        self._add("mined_terms", (
            term.lower(), display, acronym, inferred_type, frequency, doc_frequency, salience,
        ))

    # -- flushing ------------------------------------------------------------
    def _flush_table(self, table: str) -> None:
        rows = self._buffers.get(table)
        if not rows:
            return
        self.conn.executemany(_SQL[table], rows)
        self._counts[table] += len(rows)
        rows.clear()

    def flush(self) -> None:
        """Flush all buffers in dependency order and commit."""
        for table in _FLUSH_ORDER:
            self._flush_table(table)
        self.conn.commit()

    # -- aggregates ----------------------------------------------------------
    def recompute_aggregates(self) -> dict[str, int]:
        """Rebuild derived tables from persisted evidence (idempotent).

        ``concept_edges`` becomes a pure function of ``relation_evidence`` and
        ``concepts.paper_count`` a pure function of ``paper_concepts`` — so
        re-indexing the same corpus never double-counts.
        """
        import json

        self.flush()
        conn = self.conn

        # paper_count per concept
        conn.execute(
            """
            UPDATE concepts SET paper_count = COALESCE((
              SELECT COUNT(DISTINCT arxiv_id) FROM paper_concepts
              WHERE paper_concepts.concept_name = concepts.name
            ), 0)
            """
        )

        # Rebuild concept_edges from evidence with a single ordered scan.
        conn.execute("DELETE FROM concept_edges")
        cur = conn.execute(
            """
            SELECT source, target, relation, confidence, arxiv_id
            FROM relation_evidence
            ORDER BY source, target, relation
            """
        )
        edge_rows: list[tuple] = []
        cur_key: tuple | None = None
        weight = 0.0
        count = 0
        papers: list[str] = []
        seen_papers: set[str] = set()

        def emit() -> None:
            if cur_key is None:
                return
            s, t, r = cur_key
            edge_rows.append((s, t, r, round(weight, 4), count, json.dumps(papers)))

        for row in cur:
            key = (row["source"], row["target"], row["relation"])
            if key != cur_key:
                emit()
                cur_key = key
                weight, count, papers, seen_papers = 0.0, 0, [], set()
            weight += row["confidence"] or 0.0
            count += 1
            aid = row["arxiv_id"]
            if aid not in seen_papers:
                seen_papers.add(aid)
                papers.append(aid)
        emit()

        if edge_rows:
            conn.executemany(
                """
                INSERT INTO concept_edges (source, target, relation, weight, evidence_count, paper_ids_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                edge_rows,
            )
        conn.commit()
        return {"edges": len(edge_rows)}

    # -- full-text index -----------------------------------------------------
    def rebuild_fts(self) -> bool:
        """(Re)build FTS5 indexes over papers and evidence. No-op if FTS5 absent."""
        conn = self.conn
        try:
            conn.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts
                  USING fts5(arxiv_id UNINDEXED, title, abstract);
                CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts
                  USING fts5(evidence_text, source UNINDEXED, target UNINDEXED, relation UNINDEXED, arxiv_id UNINDEXED);
                """
            )
        except Exception as exc:  # noqa: BLE001 - FTS5 may be unavailable
            log.warning("FTS5 unavailable, skipping full-text index: %s", exc)
            return False

        conn.execute("DELETE FROM papers_fts")
        conn.execute(
            "INSERT INTO papers_fts (arxiv_id, title, abstract) "
            "SELECT arxiv_id, COALESCE(title,''), COALESCE(abstract,'') FROM papers"
        )
        conn.execute("DELETE FROM evidence_fts")
        conn.execute(
            "INSERT INTO evidence_fts (evidence_text, source, target, relation, arxiv_id) "
            "SELECT evidence_text, source, target, relation, arxiv_id FROM relation_evidence"
        )
        conn.commit()
        return True

    # -- lifecycle -----------------------------------------------------------
    @property
    def written(self) -> dict[str, int]:
        return dict(self._counts)

    def close(self) -> None:
        try:
            self.flush()
        finally:
            self.conn.close()

    def __enter__(self) -> BatchWriter:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()
        else:
            try:
                self.conn.rollback()
            finally:
                self.conn.close()
