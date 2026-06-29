"""Small helpers for arXiv identifiers and URLs."""

from __future__ import annotations

import re

_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
_OLD_ID_RE = re.compile(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?", re.IGNORECASE)


def normalize_arxiv_id(raw: str) -> str:
    """Return a version-stripped canonical arXiv id from many input forms.

    Accepts ``2406.01234``, ``2406.01234v2``, ``arXiv:2406.01234``,
    ``http://arxiv.org/abs/2406.01234v1``, and legacy ``quant-ph/0601001``.
    """
    raw = raw.strip()
    m = _ARXIV_ID_RE.search(raw)
    if m:
        return m.group(1)
    m = _OLD_ID_RE.search(raw)
    if m:
        return m.group(1)
    # Fall back to the last path segment with any "arXiv:" prefix removed.
    tail = raw.rstrip("/").split("/")[-1]
    return tail.replace("arXiv:", "").strip()


def arxiv_abs_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{normalize_arxiv_id(arxiv_id)}"


def arxiv_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{normalize_arxiv_id(arxiv_id)}"
