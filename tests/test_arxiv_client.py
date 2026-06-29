"""arXiv client: parsing, query building, id normalization, date filter (mocked)."""

from __future__ import annotations

from researcher_mcp.ingest.arxiv_client import ArxivClient, build_search_query
from researcher_mcp.ingest.metadata import normalize_arxiv_id

from conftest import STATIC_FEED


def test_normalize_ids():
    assert normalize_arxiv_id("http://arxiv.org/abs/2406.01234v2") == "2406.01234"
    assert normalize_arxiv_id("arXiv:2401.00099") == "2401.00099"
    assert normalize_arxiv_id("2406.01234") == "2406.01234"


def test_build_query():
    q = build_search_query(categories=["quant-ph", "cs.LG"], keywords=["tensor network", "vqe"])
    assert "cat:quant-ph" in q and "cat:cs.LG" in q
    assert 'all:"tensor network"' in q and "AND" in q


def test_parse_feed_fields():
    papers = ArxivClient.parse_feed(STATIC_FEED)
    assert len(papers) == 3
    p = papers[0]
    assert p.arxiv_id == "2606.01234"  # version stripped
    assert "QPEPS-QMERA" in p.title
    assert p.authors == ["A. Researcher", "B. Scientist"]
    assert "quant-ph" in p.categories
    assert p.published_date == "2026-06-05"
    assert "/pdf/" in p.pdf_url  # arXiv PDF links have no .pdf suffix


def test_search_with_injected_fetcher(mock_client):
    papers = mock_client.search(categories=["quant-ph"], max_results=10)
    assert len(papers) == 3
    ids = {p.arxiv_id for p in papers}
    assert {"2606.01234", "2606.05678", "2606.09999"} == ids


def test_date_filter():
    client = ArxivClient(min_interval=0.0, fetcher=lambda _u: STATIC_FEED)
    # Window excludes everything (all published 2026-06-05).
    none = client.search(categories=["quant-ph"], from_date="2026-06-10", to_date="2026-06-11")
    assert none == []
    # Window includes them.
    some = client.search(categories=["quant-ph"], from_date="2026-06-01", to_date="2026-06-30")
    assert len(some) == 3


def test_get_by_ids(mock_client):
    papers = mock_client.get_by_ids(["2606.01234"])
    assert papers and papers[0].arxiv_id == "2606.01234"
