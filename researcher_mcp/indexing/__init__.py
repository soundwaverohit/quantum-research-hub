"""Indexing layer: efficient literature ingestion into a conceptual-map database.

This package turns a stream of papers into a queryable, provenance-rich concept
graph and exports it as a first-principles training dataset for scientific
reasoning models.

Modules:
    writer          BatchWriter — single-connection, batched SQLite writes.
    term_miner      Domain-general candidate-term discovery (grows the ontology).
    graph_store     Translate extraction results into buffered graph rows.
    pipeline        Stream papers -> mine -> resolve -> relate -> persist.
    dataset_export  Emit triples / reasoning-chains / QA / contrastive JSONL.
"""

from __future__ import annotations
