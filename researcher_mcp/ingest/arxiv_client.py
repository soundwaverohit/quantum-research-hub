"""arXiv Atom API client.

Real, live arXiv search built on ``httpx`` + ``feedparser``. The network call
is isolated behind an injectable ``fetcher`` callable so tests can supply a
canned Atom feed and never touch the network (CLAUDE.md §14).

Example::

    client = ArxivClient()
    papers = client.search(categories=["quant-ph"], max_results=5)
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from datetime import date, datetime
from urllib.parse import urlencode

from ..logging_utils import get_logger
from ..storage.models import Paper
from .metadata import arxiv_pdf_url, normalize_arxiv_id

log = get_logger("ingest.arxiv")

ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "QuantumResearchHub/0.1 (local research MCP; mailto:research@localhost)"

# A fetcher takes a fully-built URL and returns the raw response bytes.
Fetcher = Callable[[str], bytes]


def _httpx_fetcher(url: str) -> bytes:
    import httpx  # imported lazily so unit tests need no network stack

    # follow_redirects handles arXiv's http->https 301 (and any future moves).
    resp = httpx.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True
    )
    resp.raise_for_status()
    return resp.content


def build_search_query(
    query: str | None = None,
    categories: Sequence[str] | None = None,
    keywords: Sequence[str] | None = None,
) -> str:
    """Build an arXiv ``search_query`` string.

    - ``query`` (if given) is used verbatim as the free-text clause.
    - ``categories`` become an OR of ``cat:`` clauses.
    - ``keywords`` become an OR of quoted ``all:`` clauses.
    Clauses are AND-ed together.
    """
    clauses: list[str] = []
    if categories:
        cats = " OR ".join(f"cat:{c}" for c in categories)
        clauses.append(f"({cats})")
    if keywords:
        kw = " OR ".join(f'all:"{k}"' for k in keywords)
        clauses.append(f"({kw})")
    if query:
        clauses.append(f"({query})")
    return " AND ".join(clauses) if clauses else "all:quantum"


class ArxivClient:
    def __init__(
        self,
        *,
        min_interval: float = 3.0,
        fetcher: Fetcher | None = None,
        api_url: str = ARXIV_API,
    ) -> None:
        self.min_interval = max(0.0, min_interval)
        self._fetch = fetcher or _httpx_fetcher
        self.api_url = api_url
        self._last_request = 0.0

    # -- internal ------------------------------------------------------------
    def _respect_rate_limit(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _build_url(
        self, search_query: str, *, start: int, max_results: int,
        sort_by: str, sort_order: str,
    ) -> str:
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        return f"{self.api_url}?{urlencode(params)}"

    @staticmethod
    def parse_feed(content: bytes) -> list[Paper]:
        """Parse a raw arXiv Atom feed into Paper models."""
        import feedparser

        feed = feedparser.parse(content)
        papers: list[Paper] = []
        for entry in feed.entries:
            arxiv_id = normalize_arxiv_id(entry.get("id", ""))
            if not arxiv_id:
                continue
            authors = [a.get("name", "").strip() for a in entry.get("authors", [])]
            authors = [a for a in authors if a]
            categories = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]
            pdf_url = ""
            for link in entry.get("links", []):
                if link.get("type") == "application/pdf":
                    pdf_url = link.get("href", "")
                    break
            if not pdf_url:
                pdf_url = arxiv_pdf_url(arxiv_id)
            papers.append(
                Paper(
                    arxiv_id=arxiv_id,
                    title=" ".join(entry.get("title", "").split()),
                    authors=authors,
                    abstract=" ".join(entry.get("summary", "").split()),
                    categories=categories,
                    published_date=_to_date(entry.get("published")),
                    updated_date=_to_date(entry.get("updated")),
                    pdf_url=pdf_url,
                )
            )
        return papers

    # -- public --------------------------------------------------------------
    def search(
        self,
        *,
        query: str | None = None,
        categories: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        max_results: int = 10,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> list[Paper]:
        """Search arXiv and return Paper models (newest first by default).

        ``from_date`` / ``to_date`` are ``YYYY-MM-DD`` strings applied as a
        client-side filter on the published date (robust against arXiv's
        finicky server-side date syntax).
        """
        search_query = build_search_query(query, categories, keywords)
        # Over-fetch a little when date-filtering so the window isn't starved.
        fetch_n = max_results if not (from_date or to_date) else min(max_results * 3, 200)
        url = self._build_url(
            search_query, start=0, max_results=fetch_n,
            sort_by=sort_by, sort_order=sort_order,
        )
        self._respect_rate_limit()
        log.info("arXiv query: %s (max=%d)", search_query, fetch_n)
        try:
            content = self._fetch(url)
        finally:
            self._last_request = time.monotonic()

        papers = self.parse_feed(content)
        papers = _filter_by_date(papers, from_date, to_date)
        return papers[:max_results]

    def get_by_ids(self, arxiv_ids: Sequence[str]) -> list[Paper]:
        """Fetch specific papers by id (uses arXiv ``id_list``)."""
        ids = [normalize_arxiv_id(i) for i in arxiv_ids if i]
        if not ids:
            return []
        url = f"{self.api_url}?{urlencode({'id_list': ','.join(ids), 'max_results': len(ids)})}"
        self._respect_rate_limit()
        try:
            content = self._fetch(url)
        finally:
            self._last_request = time.monotonic()
        return self.parse_feed(content)


def _to_date(value: str | None) -> str | None:
    if not value:
        return None
    # arXiv timestamps look like 2024-06-03T17:59:59Z
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10] if len(value) >= 10 else value


def _filter_by_date(
    papers: list[Paper], from_date: str | None, to_date: str | None
) -> list[Paper]:
    if not (from_date or to_date):
        return papers
    lo = date.fromisoformat(from_date) if from_date else date.min
    hi = date.fromisoformat(to_date) if to_date else date.max
    out: list[Paper] = []
    for p in papers:
        if not p.published_date:
            continue
        try:
            d = date.fromisoformat(p.published_date)
        except ValueError:
            continue
        if lo <= d <= hi:
            out.append(p)
    return out
