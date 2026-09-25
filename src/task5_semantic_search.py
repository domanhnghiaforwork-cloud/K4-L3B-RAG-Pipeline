"""Task 5 - semantic search over the shared ChromaDB collection."""

from __future__ import annotations

from .contracts import validate_search_results
from .task4_chunking_indexing import embed_texts, get_collection


def _restore_metadata(metadata: dict) -> dict:
    restored = dict(metadata)
    restored["url"] = restored.get("url") or None
    return restored


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Return dense SearchResults ordered by cosine similarity."""
    query = query.strip()
    if not query or top_k <= 0:
        return []

    collection = get_collection()
    count_method = getattr(collection, "count", None)
    available = count_method() if callable(count_method) else top_k
    if available <= 0:
        return []
    query_vector = embed_texts([query])[0]
    response = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, available),
        include=["documents", "metadatas", "distances"],
    )

    results: list[dict] = []
    ids = (response.get("ids") or [[]])[0]
    documents = (response.get("documents") or [[]])[0]
    metadatas = (response.get("metadatas") or [[]])[0]
    distances = (response.get("distances") or [[]])[0]
    for item_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
        results.append(
            {
                "id": item_id,
                "content": content,
                "score": max(-1.0, min(1.0, 1.0 - float(distance))),
                "metadata": _restore_metadata(metadata),
                "retrieval_method": "dense",
            }
        )

    results.sort(key=lambda item: (-item["score"], item["id"]))
    results = results[:top_k]
    validate_search_results(results, top_k=top_k, expected_method="dense")
    return results


if __name__ == "__main__":
    for result in semantic_search("test query", top_k=3):
        print(result)
