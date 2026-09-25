"""Task 8 - PageIndex vectorless fallback with a persistent document-ID cache."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .contracts import validate_search_results


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
STANDARDIZED_DIR = ROOT_DIR / "data" / "standardized"
CACHE_PATH = ROOT_DIR / "pageindex_doc_ids.json"


def _get_client():
    """Create a client compatible with the installed PageIndex SDK version."""
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("PAGEINDEX_API_KEY is not configured")
    from pageindex import PageIndexClient

    parameters = inspect.signature(PageIndexClient).parameters
    kwargs: dict = {}
    if "api_key" in parameters:
        kwargs["api_key"] = PAGEINDEX_API_KEY
    if "index" in parameters:
        kwargs["index"] = "cloud"
    if "chat" in parameters and LLM_MODEL:
        kwargs["chat"] = LLM_MODEL
    return PageIndexClient(**kwargs)


def _load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {str(key): str(value) for key, value in data.items() if value}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _extract_doc_id(response: object) -> str:
    if isinstance(response, str) and response.strip():
        return response.strip()
    if isinstance(response, dict):
        for key in ("doc_id", "document_id", "id"):
            value = response.get(key)
            if value:
                return str(value)
    for key in ("doc_id", "document_id", "id"):
        value = getattr(response, key, None)
        if value:
            return str(value)
    raise RuntimeError("PageIndex upload response did not contain a document ID")


def upload_documents() -> None:
    """Upload uncached Markdown files and persist their PageIndex document IDs."""
    files = sorted(STANDARDIZED_DIR.rglob("*.md")) if STANDARDIZED_DIR.exists() else []
    if not files:
        return
    client = _get_client()
    cache = _load_cache()
    changed = False
    for path in files:
        cache_key = path.relative_to(STANDARDIZED_DIR).as_posix()
        if cache_key in cache:
            continue
        if hasattr(client, "submit_document"):
            response = client.submit_document(str(path), wait=True)
        elif hasattr(client, "index"):
            response = client.index(str(path))
        else:
            raise RuntimeError("Installed PageIndex SDK has no document upload method")
        cache[cache_key] = _extract_doc_id(response)
        changed = True
    if changed:
        _save_cache(cache)


def _extract_answer(response: object) -> str:
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            if message.get("content"):
                return str(message["content"]).strip()
        for key in ("answer", "content", "text"):
            if response.get(key):
                return str(response[key]).strip()
    choices = getattr(response, "choices", None)
    if choices:
        content = getattr(getattr(choices[0], "message", None), "content", None)
        if content:
            return str(content).strip()
    return ""


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Query all cached PageIndex documents and return fallback evidence."""
    query = query.strip()
    if not query or top_k <= 0:
        return []
    if not _load_cache():
        upload_documents()
    cache = _load_cache()
    if not cache:
        return []

    client = _get_client()
    doc_ids = list(cache.values())
    if hasattr(client, "chat_completions"):
        response = client.chat_completions(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Find and return only the passages relevant to this question. "
                        f"Question: {query}"
                    ),
                }
            ],
            doc_id=doc_ids,
        )
    elif hasattr(client, "chat"):
        response = client.chat(query, doc_id=doc_ids)
    else:
        raise RuntimeError("Installed PageIndex SDK has no supported query method")

    answer = _extract_answer(response)
    if not answer:
        return []
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    source_names = list(cache.keys())
    source_label = ", ".join(source_names[:3])
    if len(source_names) > 3:
        source_label += f" (+{len(source_names) - 3} files)"
    result = {
        "id": f"pageindex::{digest}",
        "content": answer,
        "score": 1.0,
        "metadata": {
            "source": source_label,
            "title": f"PageIndex fallback across {len(doc_ids)} documents",
            "doc_type": "legal",
            "url": None,
            "chunk_index": 0,
        },
        "retrieval_method": "pageindex",
    }
    results = [result][:top_k]
    validate_search_results(results, top_k=top_k, expected_method="pageindex")
    return results


if __name__ == "__main__":
    upload_documents()
