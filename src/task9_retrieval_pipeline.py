"""Task 9 - dense/BM25/RRF retrieval with PageIndex fallback."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search


load_dotenv()


def _configured_threshold() -> float:
    raw = os.getenv("SCORE_THRESHOLD", "").strip()
    if not raw:
        return 0.3
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError("SCORE_THRESHOLD must be a number") from error


SCORE_THRESHOLD = _configured_threshold()
DEFAULT_TOP_K = 5


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Return hybrid/PageIndex results, or dense results for the A/B baseline."""
    query = query.strip()
    if not query or top_k <= 0:
        return []

    candidate_count = max(top_k * 2, top_k)
    dense = semantic_search(query, top_k=candidate_count)
    if use_reranking:
        sparse = lexical_search(query, top_k=candidate_count)
        primary = rerank_rrf([dense, sparse], top_k=top_k)
    else:
        primary = dense[:top_k]

    best_dense_score = float(dense[0]["score"]) if dense else 0.0
    if best_dense_score < score_threshold:
        try:
            fallback = pageindex_search(query, top_k=top_k)
            if fallback:
                return fallback
        except Exception:
            # PageIndex is optional at runtime; the primary retriever stays usable.
            pass
    return primary[:top_k]


if __name__ == "__main__":
    for result in retrieve("test query", top_k=3):
        print(result)
