"""Task 1: download official legal documents for Vietnamese household businesses."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

# Official PDFs published by the Government of Vietnam. Together they cover
# business registration, e-commerce tax, and electronic invoices.
DOCUMENT_SOURCES = {
    "nghi_dinh_168_2025_dang_ky_doanh_nghiep.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/7/168nd.signed.pdf"
    ),
    "nghi_dinh_117_2025_thue_thuong_mai_dien_tu.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/6/117-ndcp.signed.pdf"
    ),
    "nghi_dinh_70_2025_hoa_don_chung_tu.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/3/70-nd-cp.signed.pdf"
    ),
}

USER_AGENT = "Mozilla/5.0 (compatible; VinUni-RAG-Corpus/1.0)"


def setup_directory() -> None:
    """Create the directory that stores original legal documents."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def _download_pdf(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=90) as response:
        content = response.read()

    if not content.startswith(b"%PDF-"):
        raise ValueError(f"The response is not a PDF: {url}")
    if len(content) <= 1024:
        raise ValueError(f"The downloaded PDF is unexpectedly small: {url}")
    return content


def download_documents() -> None:
    """Download three public, official PDFs and preserve their original bytes."""
    setup_directory()

    def download_one(filename: str, url: str) -> Path:
        output = DATA_DIR / filename
        if output.exists() and output.stat().st_size > 1024:
            with output.open("rb") as existing:
                if existing.read(5) == b"%PDF-":
                    return output

        content = _download_pdf(url)
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
            output = job.result()
            print(f"Ready: {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    download_documents()
