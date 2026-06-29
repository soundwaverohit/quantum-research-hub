"""Paper memory search."""

from __future__ import annotations

from researcher_mcp.tools import memory_tools, paper_tools


def _ingest(mock_client):
    for aid in ("2606.01234", "2606.05678", "2606.09999"):
        paper_tools.ingest_paper(aid, client=mock_client)


def test_search_ranks_relevant_first(mock_client):
    _ingest(mock_client)
    out = memory_tools.search_paper_memory("tensor network ansatz ising vqe", k=3)
    assert out["results"], "expected at least one hit"
    assert out["results"][0]["arxiv_id"] == "2606.01234"
    assert out["results"][0]["score"] > 0
    assert out["results"][0]["snippet"]


def test_circuit_cutting_query(mock_client):
    _ingest(mock_client)
    out = memory_tools.search_paper_memory("circuit cutting distributed heisenberg", k=3)
    assert out["results"][0]["arxiv_id"] == "2606.05678"


def test_bm25_backend_still_available(mock_client, monkeypatch):
    from researcher_mcp.config import reset_config_cache

    monkeypatch.setenv("QRH_MEMORY_BACKEND", "bm25")
    reset_config_cache()
    _ingest(mock_client)
    out = memory_tools.search_paper_memory("tensor network ansatz ising vqe", k=3)
    assert out["results"][0]["arxiv_id"] == "2606.01234"


def test_empty_query_returns_error():
    out = memory_tools.search_paper_memory("   ")
    assert out["results"] == []
    assert "error" in out
