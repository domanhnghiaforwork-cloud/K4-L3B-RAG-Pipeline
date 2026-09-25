"""Task 4 - load, chunk, embed and index the normalized corpus."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .contracts import validate_document


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
STANDARDIZED_DIR = ROOT_DIR / "data" / "standardized"
CHROMA_DIR = ROOT_DIR / "chroma_db"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = 1024
COLLECTION_NAME = "rag_documents"
METADATA_PREFIX = "<!-- rag-metadata: "


@lru_cache(maxsize=1)
def _get_sentence_transformer():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the configured provider and return plain Python lists."""
    if not texts:
        return []
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Every text passed to embed_texts must be non-empty")

    if EMBEDDING_PROVIDER in {"sentence_transformers", "sentence-transformers", "local"}:
        vectors = _get_sentence_transformer().encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    if EMBEDDING_PROVIDER == "openai":
        from openai import OpenAI

        response = OpenAI().embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER}")


def get_collection():
    """Open the persistent Chroma collection configured for cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _parse_markdown(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8").strip()
    metadata: dict = {}
    content = raw
    if raw.startswith(METADATA_PREFIX):
        first_line, _, remainder = raw.partition("\n")
        payload = first_line[len(METADATA_PREFIX) :]
        if payload.endswith(" -->"):
            payload = payload[:-4]
        metadata = json.loads(payload)
        content = remainder.strip()
    return metadata, content


def load_documents() -> list[dict]:
    """Read normalized Markdown files and return contract-valid Documents."""
    documents: list[dict] = []
    if not STANDARDIZED_DIR.exists():
        return documents

    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        metadata, content = _parse_markdown(path)
        relative = path.relative_to(STANDARDIZED_DIR)
        doc_type = "legal" if "legal" in relative.parts else "news"
        document = {
            "id": relative.as_posix(),
            "content": content,
            "metadata": {
                "source": str(metadata.get("source") or path.name),
                "title": str(metadata.get("title") or path.stem),
                "doc_type": str(metadata.get("doc_type") or doc_type),
                "url": metadata.get("url") or None,
            },
        }
        validate_document(document)
        documents.append(document)
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Split Documents into stable, metadata-preserving chunks."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
        length_function=len,
    )
    chunks: list[dict] = []
    seen_ids: set[str] = set()
    for document in documents:
        validate_document(document)
        for index, text in enumerate(splitter.split_text(document["content"])):
            if not text.strip():
                continue
            chunk = {
                "id": f"{document['id']}::chunk-{index}",
                "content": text.strip(),
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            if chunk["id"] in seen_ids:
                raise ValueError(f"Duplicate chunk ID: {chunk['id']}")
            validate_document(chunk, require_chunk=True)
            seen_ids.add(chunk["id"])
            chunks.append(chunk)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Return copies of chunks augmented with embeddings."""
    if not chunks:
        return []
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("Embedding provider returned an unexpected vector count")
    return [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]


def _chroma_metadata(metadata: dict) -> dict:
    """Convert optional values to scalar values accepted by ChromaDB."""
    return {**metadata, "url": metadata.get("url") or ""}


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Idempotently upsert embedded chunks into ChromaDB."""
    if not chunks:
        return
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
        if not isinstance(chunk.get("embedding"), list) or not chunk["embedding"]:
            raise ValueError(f"Chunk has no embedding: {chunk.get('id')}")

    collection = get_collection()
    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[_chroma_metadata(chunk["metadata"]) for chunk in chunks],
    )


def run_pipeline() -> None:
    """Run the complete offline indexing pipeline."""
    documents = load_documents()
    if not documents:
        print(f"No Markdown documents found in: {STANDARDIZED_DIR}")
        return
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks from {len(documents)} documents")


if __name__ == "__main__":
    run_pipeline()
