"""Task 6 - BM25 lexical search over the same chunks stored in ChromaDB."""

from __future__ import annotations

import re

from .contracts import validate_search_results
from .task4_chunking_indexing import get_collection


CORPUS: list[dict] = []
TOKEN_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Apply a deterministic Unicode-aware tokenizer suitable for BM25."""
    return TOKEN_PATTERN.findall(text.casefold())


def load_corpus() -> list[dict]:
    """Load the canonical chunk corpus from ChromaDB."""
    response = get_collection().get(include=["documents", "metadatas"])
    items: list[dict] = []
    for item_id, content, metadata in zip(
        response.get("ids") or [],
        response.get("documents") or [],
        response.get("metadatas") or [],
    ):
        normalized_metadata = dict(metadata)
        normalized_metadata["url"] = normalized_metadata.get("url") or None
        items.append(
            {"id": item_id, "content": content, "metadata": normalized_metadata}
        )
    return items


def build_bm25_index(corpus: list[dict]):
    """Build a BM25Okapi index from chunk contents."""
    from rank_bm25 import BM25Okapi

    if not corpus:
        return None
    return BM25Okapi([tokenize(item["content"]) for item in corpus])


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Return BM25 SearchResults ordered by descending lexical score."""
    query = query.strip()
    if not query or top_k <= 0:
        return []
    corpus = CORPUS if CORPUS else load_corpus()
    if not corpus:
        return []
    bm25 = build_bm25_index(corpus)
    query_tokens = tokenize(query)
    query_token_set = set(query_tokens)
    scores = bm25.get_scores(query_tokens)
    ranked_indices = sorted(
        range(len(corpus)),
        key=lambda index: (-float(scores[index]), corpus[index]["id"]),
    )

    results: list[dict] = []
    for index in ranked_indices:
        score = float(scores[index])
        # BM25 can be exactly zero in very small corpora even for an exact
        # match (IDF=0). Keep true lexical matches and discard non-matches.
        if not query_token_set.intersection(tokenize(corpus[index]["content"])):
            continue
        item = corpus[index]
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": score,
                "metadata": dict(item["metadata"]),
                "retrieval_method": "bm25",
            }
        )
        if len(results) >= top_k:
            break

    validate_search_results(results, top_k=top_k, expected_method="bm25")
    return results


if __name__ == "__main__":
    for result in lexical_search("test query", top_k=3):
        print(result)
