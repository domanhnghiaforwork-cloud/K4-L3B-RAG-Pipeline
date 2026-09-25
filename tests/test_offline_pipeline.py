"""Offline integration tests that need neither the real corpus nor external APIs."""

from __future__ import annotations

import json


def search_result(
    item_id: str = "chunk-0", method: str = "hybrid", score: float = 0.9
) -> dict:
    return {
        "id": item_id,
        "content": "Sinh viên nộp học phí theo từng học kỳ.",
        "score": score,
        "metadata": {
            "source": "hoc_phi.md",
            "title": "Quy định học phí",
            "doc_type": "legal",
            "url": None,
            "chunk_index": 0,
        },
        "retrieval_method": method,
    }


def test_news_conversion_preserves_metadata(tmp_path, monkeypatch):
    import src.task3_convert_markdown as conversion
    import src.task4_chunking_indexing as indexing

    landing = tmp_path / "landing"
    standardized = tmp_path / "standardized"
    news_dir = landing / "news"
    news_dir.mkdir(parents=True)
    article = {
        "url": "https://example.edu/hoc-phi",
        "title": "Thông báo học phí",
        "date_crawled": "2026-09-25T10:00:00",
        "content_markdown": "Sinh viên nộp học phí theo từng học kỳ.",
    }
    (news_dir / "article_01.json").write_text(
        json.dumps(article, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(conversion, "LANDING_DIR", landing)
    monkeypatch.setattr(conversion, "OUTPUT_DIR", standardized)
    monkeypatch.setattr(indexing, "STANDARDIZED_DIR", standardized)

    conversion.convert_news_articles()
    documents = indexing.load_documents()

    assert len(documents) == 1
    assert documents[0]["metadata"]["title"] == article["title"]
    assert documents[0]["metadata"]["url"] == article["url"]
    assert documents[0]["metadata"]["doc_type"] == "news"


def test_generation_maps_citations_to_reordered_sources(monkeypatch):
    import src.task10_generation as generation

    chunks = [
        search_result(f"chunk-{index}", score=0.9 - index * 0.1)
        for index in range(3)
    ]
    monkeypatch.setattr(generation, "retrieve", lambda query, top_k: chunks)
    monkeypatch.setattr(
        generation,
        "call_llm",
        lambda system_prompt, user_message: "Học phí được nộp theo học kỳ [S1].",
    )

    result = generation.generate_with_citation("Nộp học phí khi nào?", top_k=3)

    assert result["answer"].endswith("[S1].")
    assert result["sources"][0]["id"] == "chunk-0"
    assert result["retrieval_source"] == "hybrid"


def test_generation_returns_safe_refusal_when_provider_fails(monkeypatch):
    import src.task10_generation as generation

    monkeypatch.setattr(generation, "retrieve", lambda query, top_k: [search_result()])

    def unavailable(system_prompt, user_message):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(generation, "call_llm", unavailable)
    result = generation.generate_with_citation("Nộp học phí khi nào?")

    assert result["answer"] == generation.SAFE_REFUSAL
    assert result["sources"]


def test_dense_only_mode_does_not_run_bm25(monkeypatch):
    import src.task9_retrieval_pipeline as pipeline

    dense = [search_result(method="dense")]
    monkeypatch.setattr(pipeline, "semantic_search", lambda query, top_k: dense)

    def must_not_run(query, top_k):
        raise AssertionError("BM25 must not run in the dense-only baseline")

    monkeypatch.setattr(pipeline, "lexical_search", must_not_run)
    output = pipeline.retrieve(
        "Nộp học phí khi nào?",
        top_k=1,
        score_threshold=0.0,
        use_reranking=False,
    )
    assert output == dense


def test_pageindex_upload_is_cached(tmp_path, monkeypatch):
    import src.task8_pageindex_vectorless as pageindex

    standardized = tmp_path / "standardized"
    document = standardized / "legal" / "policy.md"
    document.parent.mkdir(parents=True)
    document.write_text("# Policy\n\nPolicy content", encoding="utf-8")
    calls = []

    class FakeClient:
        def submit_document(self, path, wait=True):
            calls.append((path, wait))
            return {"doc_id": "doc-123"}

    monkeypatch.setattr(pageindex, "STANDARDIZED_DIR", standardized)
    monkeypatch.setattr(pageindex, "CACHE_PATH", tmp_path / "pageindex_doc_ids.json")
    monkeypatch.setattr(pageindex, "_get_client", lambda: FakeClient())

    pageindex.upload_documents()
    pageindex.upload_documents()

    assert len(calls) == 1
    assert pageindex._load_cache() == {"legal/policy.md": "doc-123"}


def test_pageindex_search_normalizes_provider_answer(tmp_path, monkeypatch):
    import src.task8_pageindex_vectorless as pageindex

    cache_path = tmp_path / "pageindex_doc_ids.json"
    cache_path.write_text('{"legal/policy.md": "doc-123"}', encoding="utf-8")

    class FakeClient:
        def chat_completions(self, messages, doc_id):
            assert doc_id == ["doc-123"]
            return {"choices": [{"message": {"content": "Relevant policy passage"}}]}

    monkeypatch.setattr(pageindex, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pageindex, "_get_client", lambda: FakeClient())
    output = pageindex.pageindex_search("What is the policy?", top_k=2)

    assert output[0]["retrieval_method"] == "pageindex"
    assert output[0]["content"] == "Relevant policy passage"


def test_empty_vectorstore_does_not_load_embedding_model(monkeypatch):
    import src.task5_semantic_search as semantic

    class EmptyCollection:
        def count(self):
            return 0

    monkeypatch.setattr(semantic, "get_collection", lambda: EmptyCollection())

    def must_not_embed(texts):
        raise AssertionError("Embedding model must not load for an empty collection")

    monkeypatch.setattr(semantic, "embed_texts", must_not_embed)
    assert semantic.semantic_search("test query") == []
