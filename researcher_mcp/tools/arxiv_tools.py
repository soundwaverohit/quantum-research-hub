"""arXiv search tool (MCP contract: ``search_arxiv``)."""

from __future__ import annotations

from collections.abc import Sequence

from ..config import get_config
from ..ingest.arxiv_client import ArxivClient
from ..logging_utils import get_logger

log = get_logger("tools.arxiv")


def search_arxiv(
    query: str | None = None,
    categories: Sequence[str] | None = None,
    keywords: Sequence[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    max_results: int = 10,
    *,
    client: ArxivClient | None = None,
) -> dict:
    """Search arXiv for papers by free-text query, categories, keywords, and dates.

    Args:
        query: Optional free-text clause (arXiv query syntax).
        categories: arXiv categories to OR together (e.g. ``["quant-ph"]``).
        keywords: Phrases to OR together as ``all:"..."`` clauses.
        from_date / to_date: ``YYYY-MM-DD`` client-side published-date filter.
        max_results: Max papers to return (capped by config).
        client: Injected client (tests pass a mock; default hits live arXiv).

    Returns:
        ``{"papers": [ {arxiv_id,title,authors,abstract,categories,published,pdf_url} ]}``
        or ``{"error": "..."}``.
    """
    cfg = get_config()
    max_results = min(max_results, cfg.arxiv_max_results)
    if not (query or categories or keywords):
        categories = cfg.categories  # sensible default: tracked categories
    client = client or ArxivClient(min_interval=cfg.arxiv_min_interval)
    try:
        papers = client.search(
            query=query, categories=categories, keywords=keywords,
            from_date=from_date, to_date=to_date, max_results=max_results,
        )
    except Exception as exc:  # noqa: BLE001 - return structured error
        log.warning("search_arxiv failed: %s", exc)
        return {"error": f"arXiv search failed: {exc}", "papers": []}

    return {
        "papers": [
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "categories": p.categories,
                "published": p.published_date,
                "pdf_url": p.pdf_url,
            }
            for p in papers
        ]
    }
