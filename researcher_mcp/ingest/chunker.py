"""Deterministic text chunking.

Splits raw text into overlapping word-windows. Used for full-text ingestion
and to feed the lexical memory index. Pure-Python, no dependencies.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..storage.models import PaperChunk


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~0.75 words/token)."""
    return int(len(text.split()) / 0.75) + 1


def chunk_text(
    text: str, *, words_per_chunk: int = 220, overlap: int = 40
) -> Iterator[str]:
    words = text.split()
    if not words:
        return
    step = max(1, words_per_chunk - overlap)
    for start in range(0, len(words), step):
        window = words[start : start + words_per_chunk]
        if window:
            yield " ".join(window)
        if start + words_per_chunk >= len(words):
            break


def make_chunks(
    arxiv_id: str, text: str, *, section: str = "body",
    words_per_chunk: int = 220, overlap: int = 40,
) -> list[PaperChunk]:
    chunks: list[PaperChunk] = []
    for idx, body in enumerate(
        chunk_text(text, words_per_chunk=words_per_chunk, overlap=overlap)
    ):
        chunks.append(
            PaperChunk(
                arxiv_id=arxiv_id,
                section=section,
                chunk_index=idx,
                chunk_text=body,
                token_estimate=estimate_tokens(body),
            )
        )
    return chunks
