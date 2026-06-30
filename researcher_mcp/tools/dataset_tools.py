"""MCP tools for the indexing pipeline and dataset export.

  build_concept_index   — (re)build the concept map from stored papers.
  get_index_stats       — headline counts for the concept-map index.
  export_reasoning_dataset — emit the first-principles training dataset (JSONL).
"""

from __future__ import annotations

from ..indexing import dataset_export, pipeline

_VALID_FORMATS = ("triples", "chains", "qa", "contrastive")


def build_concept_index(reset: bool = False, limit: int | None = None) -> dict:
    """Rebuild the concept-map index from every paper currently stored.

    Args:
        reset: clear mined concepts + evidence first (seed ontology is kept).
        limit: cap the number of papers processed.

    Returns the build stats dict.
    """
    return pipeline.rebuild_index(reset=reset, limit=limit)


def get_index_stats() -> dict:
    """Return concept/edge/evidence/mined-term counts for the index."""
    return pipeline.get_index_stats()


def export_reasoning_dataset(formats: list[str] | None = None, min_confidence: float = 0.5) -> dict:
    """Export the concept map as a first-principles reasoning dataset (JSONL).

    Args:
        formats: any of triples, chains, qa, contrastive (default: all).
        min_confidence: drop relation evidence below this confidence.

    Returns {"out_dir", "files": {format: {path, count}}, "total"}.
    """
    if formats:
        formats = [f for f in formats if f in _VALID_FORMATS]
    return dataset_export.export_dataset(formats or None, min_confidence=min_confidence)
