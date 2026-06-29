"""Optional PDF downloader.

Only invoked when full-text ingestion is explicitly requested. The MVP's daily
loop builds cards from metadata + abstract and does not require PDFs.
"""

from __future__ import annotations

from pathlib import Path

from ..config import get_config
from ..logging_utils import get_logger
from .arxiv_client import USER_AGENT
from .metadata import arxiv_pdf_url, normalize_arxiv_id

log = get_logger("ingest.pdf_downloader")


def download_pdf(arxiv_id: str, *, force: bool = False) -> Path | None:
    """Download a paper PDF to ``data/papers/pdfs/<id>.pdf``.

    Returns the local path, or ``None`` on failure. Never raises on network
    errors — the caller decides how to proceed without a PDF.
    """
    cfg = get_config()
    cfg.pdf_dir.mkdir(parents=True, exist_ok=True)
    aid = normalize_arxiv_id(arxiv_id)
    dest = cfg.pdf_dir / f"{aid}.pdf"
    if dest.exists() and not force and dest.stat().st_size > 0:
        return dest
    try:
        import httpx

        url = arxiv_pdf_url(aid)
        with httpx.stream(
            "GET", url, headers={"User-Agent": USER_AGENT},
            timeout=60.0, follow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_bytes():
                    fh.write(chunk)
        log.info("Downloaded PDF %s -> %s", aid, dest)
        return dest
    except Exception as exc:  # noqa: BLE001 - best-effort
        log.warning("PDF download failed for %s: %s", aid, exc)
        if dest.exists():
            dest.unlink(missing_ok=True)
        return None
