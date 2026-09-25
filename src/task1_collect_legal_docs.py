"""
Task 1 — Thu thập tài liệu chính sách/quy định.

Hướng dẫn:
    1. Chọn chủ đề của nhóm.
    2. Tìm tối thiểu 3 tài liệu PDF/DOCX từ nguồn công khai.
    3. Lưu file gốc vào data/landing/legal/.
    4. Đặt tên không dấu và thể hiện đúng nội dung.

Ví dụ tài liệu: học phí, học bổng, ký túc xá, quy trình đăng ký.
Nếu website chặn crawler, hãy chọn nguồn công khai khác; không vượt WAF.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

DOCUMENT_SOURCES = {
    "ielts_writing_band_descriptors.pdf": (
        "https://ielts.org/cdn/ielts-guides/"
        "ielts-writing-band-descriptors.pdf"
    ),
    "ielts_academic_writing_sample_responses.pdf": (
        "https://ielts.org/cdn/computer-delivered-sample-tests-academic-writing/"
        "ielts-academic-writing-example-responses-to-parts-1-and-2-with-band-"
        "scores-and-examiner-comments.pdf"
    ),
    "ielts_general_writing_sample_responses.pdf": (
        "https://ielts.org/cdn/computer-delivered-sample-tests-general-training-"
        "writing/ielts-general-training-writing-example-responses-to-parts-1-and-"
        "2-with-band-scores-and-examiner-comments.pdf"
    ),
}


def setup_directory() -> None:
    """Tạo thư mục lưu tài liệu gốc."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def download_documents() -> None:
    """Tải ít nhất 3 PDF/DOCX từ nguồn công khai."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    def download_one(filename: str, url: str) -> Path:
        output = DATA_DIR / filename
        if output.exists() and output.stat().st_size > 1024:
            return output

        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; IELTS-RAG-Collector/1.0)",
                "Accept": "application/pdf",
            },
        )
        with urlopen(request, timeout=60) as response:
            content = response.read()
        if len(content) <= 1024 or not content.startswith(b"%PDF"):
            raise ValueError(f"Downloaded content is not a valid PDF: {url}")

        temporary = output.with_suffix(output.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(output)
        return output

    with ThreadPoolExecutor(max_workers=len(DOCUMENT_SOURCES)) as executor:
        jobs = {
            executor.submit(download_one, filename, url): filename
            for filename, url in DOCUMENT_SOURCES.items()
        }
        for job in as_completed(jobs):
            print(f"Saved: {job.result()}")


if __name__ == "__main__":
    setup_directory()
    download_documents()
