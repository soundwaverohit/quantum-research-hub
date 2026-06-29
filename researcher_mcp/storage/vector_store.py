"""Research memory search.

Default backend: a dependency-free hashed-vector index over paper titles,
abstracts, and stored chunks. It behaves like an embedding store at the API
boundary (query vector -> nearest documents) without requiring Chroma/FAISS.

Set ``QRH_MEMORY_BACKEND=bm25`` for the old lexical ranker, or ``hybrid`` to
combine both scores. The public API (:func:`search_memory`) is unchanged.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass

from ..config import get_config
from . import repository as repo

_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with", "by",
    "is", "are", "be", "we", "our", "this", "that", "these", "those", "as", "at",
    "from", "it", "its", "can", "may", "using", "use", "used", "based", "via",
    "which", "such", "than", "then", "also", "but", "not", "no", "do", "does",
}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]+")


def tokenize(text: str) -> list[str]:
    return [
        t for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOPWORDS and len(t) > 1
    ]


@dataclass
class MemoryHit:
    arxiv_id: str
    title: str
    score: float
    snippet: str
    published: str | None = None
    relevance_score: float = 0.0
    recommended_action: str = "track"


@dataclass
class _Doc:
    arxiv_id: str
    title: str
    text: str
    tokens: list[str]
    published: str | None
    relevance_score: float
    recommended_action: str


class LexicalMemoryIndex:
    """In-memory BM25 index built from the papers table."""

    def __init__(self, docs: list[_Doc], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.N = len(docs)
        self.doc_freqs: list[Counter[str]] = [Counter(d.tokens) for d in docs]
        self.doc_len = [len(d.tokens) for d in docs]
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0
        self.idf = self._compute_idf()

    def _compute_idf(self) -> dict[str, float]:
        df: Counter[str] = Counter()
        for freqs in self.doc_freqs:
            df.update(freqs.keys())
        idf: dict[str, float] = {}
        for term, n in df.items():
            # BM25 idf with +1 to stay non-negative for small corpora.
            idf[term] = math.log(1 + (self.N - n + 0.5) / (n + 0.5))
        return idf

    def search(self, query: str, k: int = 5) -> list[MemoryHit]:
        q_terms = tokenize(query)
        if not q_terms or self.N == 0:
            return []
        scored: list[tuple[float, _Doc]] = []
        for freqs, dlen, doc in zip(self.doc_freqs, self.doc_len, self.docs):
            score = 0.0
            for term in q_terms:
                if term not in freqs:
                    continue
                idf = self.idf.get(term, 0.0)
                tf = freqs[term]
                denom = tf + self.k1 * (1 - self.b + self.b * (dlen / (self.avgdl or 1)))
                score += idf * (tf * (self.k1 + 1)) / (denom or 1)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            MemoryHit(
                arxiv_id=doc.arxiv_id,
                title=doc.title,
                score=round(score, 4),
                snippet=_make_snippet(doc.text, q_terms),
                published=doc.published,
                relevance_score=doc.relevance_score,
                recommended_action=doc.recommended_action,
            )
            for score, doc in scored[:k]
        ]


class HashedVectorMemoryIndex:
    """Sparse hashing-vector index with cosine similarity."""

    def __init__(self, docs: list[_Doc], *, dim: int = 512) -> None:
        self.docs = docs
        self.dim = dim
        self.doc_vectors = [self._embed(d.tokens) for d in docs]

    def _bucket(self, token: str) -> tuple[int, float]:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, "big")
        sign = -1.0 if (raw >> 63) else 1.0
        return raw % self.dim, sign

    @staticmethod
    def _features(tokens: list[str]) -> Counter[str]:
        features = Counter(tokens)
        features.update(f"{a}_{b}" for a, b in zip(tokens, tokens[1:]))
        return features

    def _embed(self, tokens: list[str]) -> dict[int, float]:
        features = self._features(tokens)
        vec: dict[int, float] = {}
        for token, count in features.items():
            bucket, sign = self._bucket(token)
            vec[bucket] = vec.get(bucket, 0.0) + sign * math.log1p(count)
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm <= 0:
            return {}
        return {k: v / norm for k, v in vec.items()}

    @staticmethod
    def _dot(a: dict[int, float], b: dict[int, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(k, 0.0) for k, v in a.items())

    def search(self, query: str, k: int = 5) -> list[MemoryHit]:
        q_terms = tokenize(query)
        if not q_terms or not self.docs:
            return []
        q_vec = self._embed(q_terms)
        scored: list[tuple[float, _Doc]] = []
        for vec, doc in zip(self.doc_vectors, self.docs):
            score = self._dot(q_vec, vec)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            MemoryHit(
                arxiv_id=doc.arxiv_id,
                title=doc.title,
                score=round(score, 4),
                snippet=_make_snippet(doc.text, q_terms),
                published=doc.published,
                relevance_score=doc.relevance_score,
                recommended_action=doc.recommended_action,
            )
            for score, doc in scored[:k]
        ]


def _make_snippet(text: str, q_terms: list[str], width: int = 280) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    best, best_hits = "", -1
    qset = set(q_terms)
    for s in sentences:
        hits = sum(1 for t in tokenize(s) if t in qset)
        if hits > best_hits:
            best_hits, best = hits, s
    snippet = best or text[:width]
    return snippet if len(snippet) <= width else snippet[: width - 3] + "..."


def build_index_from_db() -> LexicalMemoryIndex:
    docs: list[_Doc] = []
    for p in repo.list_papers(limit=2000, order_by="created_at DESC"):
        chunk_text = " ".join(c.chunk_text for c in repo.get_chunks(p.arxiv_id)[:8])
        text = f"{p.title}. {p.abstract}. {chunk_text}"
        docs.append(
            _Doc(
                arxiv_id=p.arxiv_id,
                title=p.title,
                text=text,
                tokens=tokenize(text),
                published=p.published_date,
                relevance_score=p.relevance_score,
                recommended_action=str(getattr(p.recommended_action, "value", p.recommended_action)),
            )
        )
    return LexicalMemoryIndex(docs)


def build_vector_index_from_db() -> HashedVectorMemoryIndex:
    return HashedVectorMemoryIndex(build_index_from_db().docs)


def _merge_hits(vector_hits: list[MemoryHit], bm25_hits: list[MemoryHit], k: int) -> list[MemoryHit]:
    by_id: dict[str, MemoryHit] = {}
    scores: dict[str, float] = {}

    def add(hits: list[MemoryHit], weight: float) -> None:
        max_score = max((h.score for h in hits), default=0.0) or 1.0
        for hit in hits:
            by_id.setdefault(hit.arxiv_id, hit)
            scores[hit.arxiv_id] = scores.get(hit.arxiv_id, 0.0) + weight * (hit.score / max_score)

    add(vector_hits, 0.55)
    add(bm25_hits, 0.45)
    ranked = sorted(by_id.values(), key=lambda h: scores.get(h.arxiv_id, 0.0), reverse=True)
    out = []
    for hit in ranked[:k]:
        hit.score = round(scores.get(hit.arxiv_id, hit.score), 4)
        out.append(hit)
    return out


def search_memory(query: str, k: int = 5) -> list[MemoryHit]:
    """Search paper memory and return the top-k hits (rebuilds index per call).

    The corpus is small for the MVP, so rebuilding per call keeps results fresh
    with no cache-invalidation logic. Swap in a persistent embedding index later.
    """
    backend = get_config().memory_backend
    if backend == "bm25":
        return build_index_from_db().search(query, k)
    if backend == "hybrid":
        return _merge_hits(
            build_vector_index_from_db().search(query, k=max(k * 2, 10)),
            build_index_from_db().search(query, k=max(k * 2, 10)),
            k,
        )
    return build_vector_index_from_db().search(query, k)
