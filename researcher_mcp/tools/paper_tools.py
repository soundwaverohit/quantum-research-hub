"""Paper ingestion + retrieval tools.

MCP contracts: ``ingest_paper``, ``get_paper_card``, ``list_recent_papers``.

The MVP ingests from metadata + abstract (no PDF into Claude). PDF download +
full-text parsing is optional and only attempted when ``download_pdf=True`` AND
the optional ``pypdf`` extra is installed.
"""

from __future__ import annotations

import json

from ..config import get_config
from ..ingest.arxiv_client import ArxivClient
from ..ingest.chunker import make_chunks
from ..ingest.paper_card import generate_card, save_card
from ..ingest.pdf_downloader import download_pdf
from ..ingest.pdf_parser import parse_pdf, pdf_available
from ..logging_utils import get_logger
from ..storage import repository as repo
from ..storage.models import Paper, PaperStatus

log = get_logger("tools.paper")


def _ingest_paper_model(
    paper: Paper,
    *,
    download_pdf_flag: bool = False,
    force: bool = False,
    use_model: bool | None = None,
    model_client=None,  # noqa: ANN001 - test seam for JsonModelClient
) -> dict:
    """Core ingestion for a Paper already in hand (used by scout + ingest_paper)."""
    repo.upsert_paper(paper)

    full_text: str | None = None
    pdf_path: str | None = None
    chunks_created = 0

    if download_pdf_flag and pdf_available():
        local = download_pdf(paper.arxiv_id, force=force)
        if local:
            pdf_path = str(local)
            parsed = parse_pdf(local)
            if parsed.ok and parsed.text.strip():
                full_text = parsed.text
                cfg = get_config()
                cfg.parsed_dir.mkdir(parents=True, exist_ok=True)
                parsed_path = cfg.parsed_dir / f"{paper.arxiv_id}.txt"
                parsed_path.write_text(full_text, encoding="utf-8")
                repo.update_paper_fields(
                    paper.arxiv_id, pdf_path=pdf_path,
                    parsed_text_path=str(parsed_path),
                )

    # Always create at least one abstract-derived chunk so paper memory has
    # content even without a PDF.
    if force or repo.count_chunks(paper.arxiv_id) == 0:
        body = full_text or paper.abstract or paper.title
        chunks = make_chunks(paper.arxiv_id, body, section="abstract" if not full_text else "body")
        chunks_created = repo.add_chunks(chunks)

    card = generate_card(
        paper,
        full_text=full_text,
        use_model=use_model,
        model_client=model_client,
    )
    card_path = save_card(card)

    repo.update_paper_fields(
        paper.arxiv_id,
        paper_card_path=str(card_path),
        relevance_score=card.relevance_score,
        novelty_score=card.novelty_score,
        implementation_score=card.implementation_difficulty,
        recommended_action=card.recommended_action.value,
        status=PaperStatus.CARDED.value,
    )
    return {
        "arxiv_id": paper.arxiv_id,
        "status": "ingested",
        "pdf_path": pdf_path,
        "chunks_created": chunks_created,
        "paper_card_path": str(card_path),
        "relevance_score": card.relevance_score,
        "recommended_action": card.recommended_action.value,
        "generated_by": card.generated_by,
        "error": None,
    }


def ingest_known_paper(
    paper: Paper,
    *,
    download_pdf: bool = False,
    force: bool = False,
    use_model: bool | None = None,
    model_client=None,  # noqa: ANN001 - test seam for JsonModelClient
) -> dict:
    """Ingest a paper whose metadata is already in hand (no arXiv round-trip).

    Used by the Paper Scout -> Summarizer pipeline, which already holds the
    metadata returned by ``search_arxiv``.
    """
    return _ingest_paper_model(
        paper,
        download_pdf_flag=download_pdf,
        force=force,
        use_model=use_model,
        model_client=model_client,
    )


def ingest_paper(
    arxiv_id: str, *, force: bool = False, download_pdf: bool = False,
    client: ArxivClient | None = None,
    use_model: bool | None = None,
    model_client=None,  # noqa: ANN001 - test seam for JsonModelClient
) -> dict:
    """Ingest a single paper by arXiv id: metadata -> chunks -> paper card -> DB.

    Args:
        arxiv_id: arXiv identifier (any common form).
        force: Re-ingest even if a card already exists.
        download_pdf: Also fetch + parse the PDF (requires the ``pdf`` extra).
        client: Injected arXiv client (tests); default hits live arXiv only if
            the paper isn't already stored.

    Returns:
        ``{arxiv_id, status: ingested|skipped|failed, pdf_path, chunks_created,
        paper_card_path, error}``.
    """
    try:
        existing = repo.get_paper(arxiv_id)
        if existing and existing.paper_card_path and not force:
            return {
                "arxiv_id": existing.arxiv_id, "status": "skipped",
                "pdf_path": existing.pdf_path, "chunks_created": 0,
                "paper_card_path": existing.paper_card_path, "error": None,
            }
        paper = existing
        if paper is None or not paper.abstract:
            cfg = get_config()
            client = client or ArxivClient(min_interval=cfg.arxiv_min_interval)
            from ..ingest.metadata import normalize_arxiv_id

            fetched = client.get_by_ids([arxiv_id])
            target = normalize_arxiv_id(arxiv_id)
            paper = next((p for p in fetched if p.arxiv_id == target), None)
            if paper is None:
                return {
                    "arxiv_id": arxiv_id, "status": "failed", "pdf_path": None,
                    "chunks_created": 0, "paper_card_path": None,
                    "error": "paper not found on arXiv",
                }
        return _ingest_paper_model(
            paper,
            download_pdf_flag=download_pdf,
            force=force,
            use_model=use_model,
            model_client=model_client,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_paper(%s) failed: %s", arxiv_id, exc)
        return {
            "arxiv_id": arxiv_id, "status": "failed", "pdf_path": None,
            "chunks_created": 0, "paper_card_path": None, "error": str(exc),
        }


def get_paper_card(arxiv_id: str) -> dict:
    """Return the compact paper card for a paper (from disk, or regenerated)."""
    paper = repo.get_paper(arxiv_id)
    if paper is None:
        return {"error": f"paper {arxiv_id} not found"}
    if paper.paper_card_path:
        try:
            return json.loads(open(paper.paper_card_path, encoding="utf-8").read())
        except OSError:
            pass  # fall through to regenerate
    card = generate_card(paper)
    return card.model_dump(mode="json")


def list_recent_papers(days: int = 7, min_relevance: float = 0.0, limit: int = 100) -> dict:
    """List recently-seen papers, optionally filtered by minimum relevance."""
    papers = repo.list_papers(days=days, min_relevance=min_relevance, limit=limit)
    return {
        "count": len(papers),
        "papers": [
            {
                "arxiv_id": p.arxiv_id, "title": p.title, "published": p.published_date,
                "categories": p.categories, "relevance_score": p.relevance_score,
                "novelty_score": p.novelty_score,
                "recommended_action": str(getattr(p.recommended_action, "value", p.recommended_action)),
                "status": str(getattr(p.status, "value", p.status)),
            }
            for p in papers
        ],
    }
