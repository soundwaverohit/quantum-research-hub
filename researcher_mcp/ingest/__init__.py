"""Deterministic, cheap paper-ingestion pipeline.

    arXiv metadata -> relevance prefilter -> (optional) PDF download/parse ->
    chunk -> paper card -> DB

By design the heavy/expensive steps (PDF download, full-text parsing) are
optional. The MVP builds paper cards from metadata + abstract and never feeds
full PDFs to Claude.
"""
