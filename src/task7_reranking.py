"""Task 7 - reciprocal rank fusion (RRF)."""

from __future__ import annotations

from .contracts import validate_search_results


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Fuse rankings by ID without mixing incompatible raw score scales."""
    if top_k <= 0:
        return []
    if k < 0:
        raise ValueError("RRF k must be non-negative")

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    first_seen: dict[str, int] = {}
    encounter_order = 0
    for ranked_list in ranked_lists:
        seen_in_list: set[str] = set()
        for rank, item in enumerate(ranked_list, start=1):
            item_id = item["id"]
            if item_id in seen_in_list:
                continue
            seen_in_list.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            if item_id not in items:
                items[item_id] = item
                first_seen[item_id] = encounter_order
                encounter_order += 1

    ranked_ids = sorted(
        scores,
        key=lambda item_id: (-scores[item_id], first_seen[item_id], item_id),
    )
    results: list[dict] = []
    for item_id in ranked_ids[:top_k]:
        result = dict(items[item_id])
        result["metadata"] = dict(result["metadata"])
        result["score"] = scores[item_id]
        result["retrieval_method"] = "hybrid"
        results.append(result)

    validate_search_results(results, top_k=top_k, expected_method="hybrid")
    return results


if __name__ == "__main__":
    print("RRF is ready; run pytest tests/test_contracts.py -q")
