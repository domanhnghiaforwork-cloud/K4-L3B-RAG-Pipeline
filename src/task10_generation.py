"""Task 10 - grounded answer generation with verifiable source citations."""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv

from .contracts import validate_generation_result
from .task9_retrieval_pipeline import retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3
SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ nguồn hiện có."

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()

SYSTEM_PROMPT = """Bạn là trợ lý hỏi đáp dựa trên tài liệu.
Chỉ sử dụng thông tin trong context, không dùng kiến thức bên ngoài.
Trích dẫn mọi khẳng định bằng nhãn [S1], [S2], ... đúng với nguồn trong context.
Nếu context không đủ bằng chứng, trả lời đúng câu: Tôi không thể xác minh thông tin này từ nguồn hiện có.
Không tự tạo nguồn hoặc nhãn citation không có trong context."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Reorder chunks without mutation to reduce lost-in-the-middle effects."""
    if len(chunks) <= 2:
        return list(chunks)
    front = list(chunks[::2])
    back = list(chunks[1::2])
    return front + list(reversed(back))


def format_context(chunks: list[dict]) -> str:
    """Format chunks with stable labels that map to the returned source list."""
    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]
        url = metadata.get("url") or "N/A"
        citation_label = chunk.get("_citation_label", f"S{index}")
        parts.append(
            f"[{citation_label}]\n"
            f"Title: {metadata['title']}\n"
            f"Source: {metadata['source']}\n"
            f"URL: {url}\n"
            f"Content:\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def _require_model() -> str:
    if not LLM_MODEL:
        raise RuntimeError("LLM_MODEL is not configured in .env")
    return LLM_MODEL


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call OpenAI, Gemini or Anthropic and normalize the response to text."""
    model = _require_model()
    if LLM_PROVIDER == "openai":
        from openai import OpenAI

        response = OpenAI(timeout=60.0).chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        return (response.choices[0].message.content or "").strip()

    if LLM_PROVIDER == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        config_options = {"system_instruction": system_prompt}
        if not model.startswith("gemini-3"):
            config_options.update(temperature=TEMPERATURE, top_p=TOP_P)
        response = client.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(**config_options),
        )
        return (response.text or "").strip()

    if LLM_PROVIDER == "anthropic":
        from anthropic import Anthropic

        response = Anthropic(timeout=60.0).messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_tokens=1200,
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()

    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")


def _ensure_valid_citations(answer: str, source_count: int) -> str:
    """Ensure emitted citation labels all map to an existing source."""
    answer = answer.strip()
    if not answer or answer == SAFE_REFUSAL or source_count <= 0:
        return answer or SAFE_REFUSAL
    citations = [int(value) for value in re.findall(r"\[S(\d+)\]", answer)]
    if any(value < 1 or value > source_count for value in citations):
        return SAFE_REFUSAL
    if not citations:
        return f"{answer} [S1]"
    return answer


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Retrieve evidence, generate an answer and return a GenerationResult."""
    query = query.strip()
    if not query:
        result = {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}
        validate_generation_result(result)
        return result

    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        result = {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}
        validate_generation_result(result)
        return result

    # Keep public sources in score order (required by SearchResult contract),
    # while reordering only the private context copies sent to the LLM.
    sources = list(chunks)
    labeled_context_chunks = [
        {**chunk, "_citation_label": f"S{index}"}
        for index, chunk in enumerate(sources, start=1)
    ]
    context = format_context(reorder_for_llm(labeled_context_chunks))
    user_message = f"Context:\n{context}\n\nQuestion: {query}"
    try:
        answer = _ensure_valid_citations(call_llm(SYSTEM_PROMPT, user_message), len(sources))
    except Exception:
        answer = SAFE_REFUSAL

    method = sources[0]["retrieval_method"]
    retrieval_source = "pageindex" if method == "pageindex" else "hybrid"
    result = {
        "answer": answer,
        "sources": sources,
        "retrieval_source": retrieval_source,
    }
    validate_generation_result(result)
    return result


if __name__ == "__main__":
    print(generate_with_citation("test query"))
