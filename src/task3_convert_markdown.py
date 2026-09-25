"""Task 3 - convert raw legal documents and articles to normalized Markdown."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
LANDING_DIR = ROOT_DIR / "data" / "landing"
OUTPUT_DIR = ROOT_DIR / "data" / "standardized"
OCR_CACHE_DIR = ROOT_DIR / "data" / "_tmp_pdf"

LEGAL_EXTENSIONS = {".pdf", ".doc", ".docx"}
METADATA_PREFIX = "<!-- rag-metadata: "


def _metadata_header(metadata: dict) -> str:
    """Serialize metadata in a machine-readable Markdown comment."""
    payload = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return f"{METADATA_PREFIX}{payload} -->\n\n"


def _write_markdown(path: Path, metadata: dict, content: str) -> None:
    """Write one normalized Markdown file and reject empty conversions."""
    normalized = content.strip()
    if not normalized:
        raise ValueError(f"Converted content is empty: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_metadata_header(metadata) + normalized + "\n", encoding="utf-8")


def _configure_tesseract() -> None:
    """Make a user/system Tesseract installation discoverable by OCRmyPDF."""
    if not shutil.which("tesseract") and os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Tesseract-OCR",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "Tesseract-OCR",
        ]
        for directory in candidates:
            if (directory / "tesseract.exe").is_file():
                os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
                break

    executable = shutil.which("tesseract")
    if not executable:
        raise RuntimeError(
            "This PDF is image-only and requires Tesseract OCR. "
            "Install Tesseract with Vietnamese language data, then rerun Task 3."
        )

    if not os.getenv("TESSDATA_PREFIX"):
        tessdata_candidates = [
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Tesseract-OCR"
            / "tessdata",
            Path(executable).resolve().parent / "tessdata",
        ]
        for directory in tessdata_candidates:
            if (directory / "vie.traineddata").is_file():
                os.environ["TESSDATA_PREFIX"] = str(directory)
                break


def _ocr_scanned_pdf(source_path: Path, converter: object) -> str:
    """OCR an image-only PDF into an ignored cache and return extracted text."""
    _configure_tesseract()
    try:
        import ocrmypdf
    except ImportError as error:
        raise RuntimeError(
            "This PDF is image-only. Install project dependencies including OCRmyPDF."
        ) from error

    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ocr_path = OCR_CACHE_DIR / f"{source_path.stem}.ocr.pdf"
    if ocr_path.is_file() and ocr_path.stat().st_mtime >= source_path.stat().st_mtime:
        cached = getattr(converter.convert(str(ocr_path)), "text_content", "")
        if cached.strip():
            print(f"Reusing OCR cache: {ocr_path.name}")
            return cached

    if ocr_path.exists():
        ocr_path.unlink()
    print(f"OCR image-only PDF: {source_path.name}")
    ocrmypdf.ocr(
        source_path,
        ocr_path,
        language=["vie", "eng"],
        output_type="pdf",
        optimize=0,
        deskew=True,
        rotate_pages=True,
        invalidate_digital_signatures=True,
        progress_bar=False,
    )
    content = getattr(converter.convert(str(ocr_path)), "text_content", "")
    if not content.strip():
        raise ValueError(f"OCR produced no text: {source_path.name}")
    return content


def convert_legal_docs() -> None:
    """Convert every PDF/DOC/DOCX in ``landing/legal`` to Markdown."""
    from markitdown import MarkItDown

    input_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    converter = MarkItDown()

    for source_path in sorted(input_dir.iterdir()):
        if not source_path.is_file() or source_path.suffix.lower() not in LEGAL_EXTENSIONS:
            continue
        result = converter.convert(str(source_path))
        content = getattr(result, "text_content", "")
        if not content.strip() and source_path.suffix.lower() == ".pdf":
            content = _ocr_scanned_pdf(source_path, converter)
        metadata = {
            "source": source_path.name,
            "title": source_path.stem.replace("_", " ").replace("-", " ").strip(),
            "doc_type": "legal",
            "url": None,
        }
        _write_markdown(output_dir / f"{source_path.stem}.md", metadata, content)


def convert_news_articles() -> None:
    """Convert article JSON files to Markdown while preserving citation metadata."""
    input_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    required = {"url", "title", "date_crawled", "content_markdown"}

    for source_path in sorted(input_dir.glob("*.json")):
        data = json.loads(source_path.read_text(encoding="utf-8"))
        missing = required.difference(data)
        if missing:
            raise ValueError(f"{source_path.name} is missing fields: {sorted(missing)}")
        if any(not str(data[field]).strip() for field in required):
            raise ValueError(f"{source_path.name} contains an empty required field")

        metadata = {
            "source": source_path.name,
            "title": str(data["title"]).strip(),
            "doc_type": "news",
            "url": str(data["url"]).strip(),
            "date_crawled": str(data["date_crawled"]).strip(),
        }
        content = f"# {metadata['title']}\n\n{str(data['content_markdown']).strip()}"
        _write_markdown(output_dir / f"{source_path.stem}.md", metadata, content)


def convert_all() -> None:
    """Convert all available landing data; empty input directories are valid."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
