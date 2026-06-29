"""Paper memory search tool (MCP contract: ``search_paper_memory``)."""

from __future__ import annotations

from ..storage.vector_store import search_memory


def search_paper_memory(query: str, k: int = 5) -> dict:
    """Search stored paper memory with the configured local retrieval backend.

    Args:
        query: Natural-language query.
        k: Number of hits to return.

    Returns:
        ``{"query", "results": [{arxiv_id,title,score,snippet,published,
        relevance_score,recommended_action}]}``.
    """
    if not query or not query.strip():
        return {"query": query, "results": [], "error": "empty query"}
    hits = search_memory(query, k=k)
    return {
        "query": query,
        "results": [
            {
                "arxiv_id": h.arxiv_id, "title": h.title, "score": h.score,
                "snippet": h.snippet, "published": h.published,
                "relevance_score": h.relevance_score,
                "recommended_action": h.recommended_action,
            }
            for h in hits
        ],
    }
