"""Task 2: crawl public guidance articles for Vietnamese household businesses."""

import asyncio
import gzip
import json
import re
import zlib
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

# Government and ministry sources covering registration, tax, invoices, and
# e-commerce. Stable, descriptive filenames are generated from this ordering.
ARTICLE_URLS = [
    "https://baochinhphu.vn/nghi-dinh-ve-dang-ky-doanh-nghiep-102250701224243146.htm",
    "https://baochinhphu.vn/cuc-thue-giai-dap-ve-chuyen-doi-hoa-don-dien-tu-102250924190106182.htm",
    "https://baochinhphu.vn/san-thuong-mai-dien-tu-nop-thue-thay-ho-kinh-doanh-co-can-xuat-hoa-don-102250929143425058.htm",
    "https://baochinhphu.vn/ra-mat-bo-tai-lieu-va-giai-phap-ho-tro-tuan-thu-chinh-sach-thue-102260720175535264.htm",
    "https://baochinhphu.vn/co-quan-thue-giai-dap-khuc-mac-khi-dung-hoa-don-dien-tu-khoi-tao-tu-may-tinh-tien-102250607195252853.htm",
]

OUTPUT_NAMES = [
    "01_dang_ky_ho_kinh_doanh.json",
    "02_chuyen_doi_hoa_don_dien_tu.json",
    "03_thue_va_hoa_don_tren_san_thuong_mai_dien_tu.json",
    "04_huong_dan_thue_ban_hang_da_kenh.json",
    "05_hoa_don_dien_tu_tu_may_tinh_tien.json",
]

USER_AGENT = "Mozilla/5.0 (compatible; VinUni-RAG-Corpus/1.0)"
CONTENT_HINT = re.compile(
    r"article|detail[-_ ]?content|content[-_ ]?detail|post[-_ ]?content|news[-_ ]?content",
    re.IGNORECASE,
)


class ArticleParser(HTMLParser):
    """Extract a readable Markdown-like representation without extra packages."""

    ignored_tags = {"script", "style", "svg", "form", "noscript", "iframe"}
    block_tags = {"p", "div", "section", "article", "blockquote", "table", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page_title: list[str] = []
        self.heading_one: list[str] = []
        self.all_parts: list[str] = []
        self.focus_parts: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._ignored_depth = 0
        self._focus_depth = 0
        self._focus_found = False

    def _append(self, value: str) -> None:
        self.all_parts.append(value)
        if self._focus_depth:
            self.focus_parts.append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return

        attr_text = " ".join(value or "" for key, value in attrs if key in {"class", "id"})
        if not self._focus_found and (tag == "article" or CONTENT_HINT.search(attr_text)):
            self._focus_found = True
            self._focus_depth = 1
        elif self._focus_depth:
            self._focus_depth += 1

        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
            self._append("\n# ")
        elif tag in {"h2", "h3", "h4"}:
            self._append(f"\n{'#' * int(tag[1])} ")
        elif tag == "li":
            self._append("\n- ")
        elif tag == "br":
            self._append("\n")
        elif tag in self.block_tags:
            self._append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        if tag in self.block_tags or tag.startswith("h"):
            self._append("\n")
        if self._focus_depth:
            self._focus_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        content = re.sub(r"\s+", " ", data).strip()
        if not content:
            return
        if self._in_title:
            self.page_title.append(content)
        if self._in_h1:
            self.heading_one.append(content)
        self._append(content + " ")

    @staticmethod
    def clean(parts: list[str]) -> str:
        content = "".join(parts)
        content = re.sub(r"[ \t]+", " ", content)
        content = re.sub(r" *\n *", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()

    @property
    def title(self) -> str:
        title = " ".join(self.heading_one).strip() or " ".join(self.page_title).strip()
        return re.sub(r"\s+", " ", title)

    @property
    def markdown(self) -> str:
        focused = self.clean(self.focus_parts)
        return focused if len(focused) >= 500 else self.clean(self.all_parts)


def _fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
        },
    )
    with urlopen(request, timeout=90) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        content_encoding = response.headers.get("Content-Encoding", "").lower()
    if content_encoding == "gzip":
        raw = gzip.decompress(raw)
    elif content_encoding == "deflate":
        raw = zlib.decompress(raw)
    return raw.decode(charset, errors="replace")


async def crawl_article(url: str) -> dict:
    """Fetch one public article and return the required serializable fields."""
    html = await asyncio.to_thread(_fetch_html, url)
    parser = ArticleParser()
    parser.feed(html)

    if not parser.title:
        raise ValueError("Could not extract article title")
    if len(parser.markdown) < 200:
        raise ValueError("Extracted article content is unexpectedly short")

    return {
        "url": url,
        "title": parser.title,
        "date_crawled": datetime.now().astimezone().isoformat(timespec="seconds"),
        "content_markdown": parser.markdown,
    }


async def crawl_all() -> None:
    """Crawl every configured URL and save one UTF-8 JSON file per article."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    for output_name, url in zip(OUTPUT_NAMES, ARTICLE_URLS, strict=True):
        try:
            article = await crawl_article(url)
            output = DATA_DIR / output_name
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved: {output}")
        except Exception as error:
            failures.append(f"{url}: {error}")
            print(f"Failed: {url} — {error}")

    if failures:
        raise RuntimeError("Could not crawl all articles:\n" + "\n".join(failures))


if __name__ == "__main__":
    asyncio.run(crawl_all())
