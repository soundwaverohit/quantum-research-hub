"""Translate extraction results into buffered concept-graph rows.

This is the bridge between the *analysis* layer (``concept_extractor`` +
``term_miner``) and the *write* layer (``BatchWriter``). It never opens its own
connection — callers pass a writer so an entire corpus can stream through one
transaction-batched connection.
"""

from __future__ import annotations

import re
from collections import Counter

from ..ingest.concept_extractor import CONCEPT_REGISTRY, ConceptExtractionResult
from .term_miner import MinedTerm, salience
from .writer import BatchWriter

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Stable concept key from a surface form: 'Bond Dimension' -> 'bond-dimension'."""
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def register_seed_ontology(writer: BatchWriter) -> int:
    """Register the curated quantum ontology (concepts + aliases). Idempotent."""
    for canon, meta in CONCEPT_REGISTRY.items():
        writer.add_concept(canon, meta.type, meta.description, list(meta.aliases), source="seed")
        for alias in meta.aliases:
            writer.add_alias(alias, canon, source="seed")
    return len(CONCEPT_REGISTRY)


def index_extraction(
    writer: BatchWriter,
    arxiv_id: str,
    result: ConceptExtractionResult,
    *,
    section: str = "abstract",
) -> dict[str, int]:
    """Buffer all rows for one paper's extraction result.

    Persists: concept upserts, per-paper concept salience + mention counts, and
    one ``relation_evidence`` row per detected relation (with offsets).
    """
    mention_counts = Counter(m.canonical for m in result.concepts)
    scores = result.concept_scores()

    for canon in result.unique_concept_names():
        meta = CONCEPT_REGISTRY.get(canon)
        if meta is None:
            continue
        # Cheap idempotent upsert keeps the concept row fresh; aliases are
        # registered once via register_seed_ontology().
        writer.add_concept(canon, meta.type, meta.description, list(meta.aliases), source="seed")
        writer.add_paper_concept(
            arxiv_id, canon,
            score=scores.get(canon, 0.0),
            mention_count=mention_counts.get(canon, 0),
        )

    edges = 0
    for rel in result.relations:
        if rel.source not in CONCEPT_REGISTRY or rel.target not in CONCEPT_REGISTRY:
            continue
        writer.add_evidence(
            arxiv_id, rel.source, rel.target, rel.relation,
            evidence_text=rel.evidence,
            char_start=rel.char_start, char_end=rel.char_end,
            section=section, confidence=rel.confidence,
        )
        edges += 1

    return {"concepts": len(mention_counts), "evidence": edges}


def promote_mined_concept(
    writer: BatchWriter, term: MinedTerm, doc_frequency: int
) -> str:
    """Add a mined candidate as a first-class concept (source='mined').

    Returns the concept's canonical slug so the caller can attach paper links.
    """
    name = slugify(term.term)
    display = term.display or term.term
    ctype = term.inferred_type or "concept"
    aliases = [term.term]
    if term.acronym:
        aliases.append(term.acronym.lower())
    writer.add_concept(name, ctype, display, aliases, source="mined")
    for alias in aliases:
        writer.add_alias(alias, name, source="mined")
    writer.add_mined_term(
        term.term, display, term.acronym, ctype,
        frequency=term.count, doc_frequency=doc_frequency,
        salience=salience(term, doc_frequency),
    )
    return name


def record_mined_term(writer: BatchWriter, term: MinedTerm, doc_frequency: int) -> None:
    """Record a candidate that was NOT promoted (stays in mined_terms for review)."""
    writer.add_mined_term(
        term.term, term.display or term.term, term.acronym, term.inferred_type,
        frequency=term.count, doc_frequency=doc_frequency,
        salience=salience(term, doc_frequency),
    )


def record_mined_paper_concept(
    writer: BatchWriter, arxiv_id: str, concept_name: str, count: int
) -> None:
    """Link a promoted mined concept to a paper that mentions it."""
    writer.add_paper_concept(arxiv_id, concept_name, score=0.0, mention_count=count)
