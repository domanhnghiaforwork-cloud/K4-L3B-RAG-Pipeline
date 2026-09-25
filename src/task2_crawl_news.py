"""
Task 2 — Crawl bài viết/thông báo.

Hướng dẫn:
    1. Điền tối thiểu 5 URL công khai vào ARTICLE_URLS.
    2. Crawl từng URL bằng Crawl4AI.
    3. Lưu mỗi bài thành một JSON trong data/landing/news/.
    4. Giữ đủ url, title, date_crawled và content_markdown.

Cài browser trước khi chạy:
    python -m playwright install chromium
    
-> Dùng Firecrawl or bất cứ công cụ nào bạn quen    
"""

import asyncio
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

VIETNAMESE_ARTICLES = {
    "https://takeielts.britishcouncil.org/prepare/ielts-academic/writing": {
        "title": "Hướng dẫn chuẩn bị IELTS Academic Writing: dạng bài, mẹo và luyện tập",
        "content_markdown": """# Chuẩn bị cho bài thi IELTS Writing

IELTS Writing đánh giá khả năng viết tiếng Anh rõ ràng, có tổ chức và chính xác. Cả IELTS Academic và IELTS General Training đều có hai phần, nhưng hình thức Task 1 khác nhau tùy loại bài thi.

## Cấu trúc bài thi

Bài thi kéo dài 60 phút. Trong IELTS Academic, Task 1 yêu cầu mô tả biểu đồ, bảng hoặc sơ đồ; trong General Training, Task 1 yêu cầu viết thư với giọng văn phù hợp. Task 2 của cả hai hình thức yêu cầu viết bài luận phản hồi một quan điểm, lập luận hoặc vấn đề. Vì Task 2 có trọng số cao hơn, thí sinh nên dành khoảng 40 phút cho phần này và 20 phút cho Task 1.

## Cách chuẩn bị hiệu quả

Trước khi viết, hãy đọc kỹ câu hỏi và chú ý các từ chỉ dẫn như “thảo luận”, “so sánh”, “giải thích” hoặc “đồng ý hay không đồng ý”. Dành vài phút lập dàn ý để xác định ý chính, cách sắp xếp đoạn và ví dụ hỗ trợ.

Mỗi đoạn nên tập trung vào một ý, bám sát câu hỏi và phát triển bằng giải thích phù hợp. Hãy kết hợp câu đơn với câu phức, sử dụng từ vựng đa dạng nhưng chính xác và tránh học thuộc bài mẫu. Cuối cùng, dành vài phút kiểm tra chính tả, dạng động từ và dấu câu. Luyện viết thường xuyên trong điều kiện giới hạn thời gian sẽ cải thiện tốc độ, khả năng tổ chức và sự tự tin.""",
    },
    "https://takeielts.britishcouncil.org/what-is-ielts/how-it-works/test-format/writing": {
        "title": "Hướng dẫn về cấu trúc và cách chấm bài thi IELTS Writing",
        "content_markdown": """# Cấu trúc và cách chấm IELTS Writing

Bài thi IELTS Writing đánh giá khả năng diễn giải, tổ chức và truyền đạt thông tin bằng tiếng Anh viết. Thí sinh hoàn thành hai phần trong 60 phút: khoảng 20 phút cho Task 1 và 40 phút cho Task 2.

## Bốn tiêu chí chấm điểm

- Mức độ hoàn thành yêu cầu ở Task 1 hoặc mức độ trả lời đề ở Task 2.
- Tính mạch lạc và liên kết.
- Vốn từ vựng.
- Độ đa dạng và chính xác của ngữ pháp.

## Task 1

Ở bài thi Academic, thí sinh mô tả những đặc điểm chính của biểu đồ, bảng, đồ thị hoặc sơ đồ. Ở General Training, thí sinh viết thư để phản hồi một tình huống với văn phong trang trọng, bán trang trọng hoặc thân mật. Bài viết cần có ít nhất 150 từ.

## Task 2

Thí sinh viết bài luận tối thiểu 250 từ để phản hồi một quan điểm, lập luận hoặc vấn đề. Đề có thể yêu cầu bảo vệ ý kiến, so sánh các quan điểm, thảo luận ưu nhược điểm hoặc đề xuất giải pháp. Lập trường phải rõ ràng và được hỗ trợ bằng lý do, giải thích hoặc ví dụ.

## Kỹ năng cần thiết

Thí sinh cần biết phân tích thông tin, nhận diện xu hướng, tóm tắt đặc điểm nổi bật và sắp xếp ý logic. Bài viết nên có bố cục rõ ràng, từ nối phù hợp và giọng văn đúng ngữ cảnh. Không nên viết dài hơn quá nhiều so với số từ tối thiểu; cần dành thời gian cuối giờ để đọc lại và sửa lỗi.""",
    },
    "https://takeielts.britishcouncil.org/blog/how-to-prepare-for-ielts-at-home": {
        "title": "Hướng dẫn tự ôn luyện IELTS tại nhà",
        "content_markdown": """# Hướng dẫn tự ôn luyện IELTS tại nhà

- Tác giả: Anna Hasper
- Cập nhật lần cuối: ngày 16 tháng 1 năm 2024

Nếu phải ôn IELTS song song với công việc hoặc học tập, bạn nên xây dựng lịch học thực tế và chia mục tiêu thành những phần nhỏ.

## Luyện Writing

Đọc bài mẫu Task 1 và Task 2 để phân tích bố cục và cách dùng ngôn ngữ. Viết hằng ngày về các chủ đề quen thuộc như giáo dục, sức khỏe hoặc môi trường, đồng thời giới hạn 20 phút cho Task 1 và 40 phút cho Task 2. Sau khi viết, đối chiếu bài với bảng mô tả band điểm để xác định phần cần cải thiện.

## Luyện Listening và Reading

Nghe BBC hoặc TED Talks để làm quen với nhiều giọng tiếng Anh. Khi chữa bài thi thử, cần phân tích nguyên nhân của từng lỗi thay vì chỉ xem đáp án. Với Reading, hãy duy trì thói quen đọc tiếng Anh mỗi ngày và rèn kỹ năng đọc lướt, tìm thông tin trong thời gian ngắn.

## Luyện Speaking

Có thể luyện nói đuổi theo một đoạn TED Talk, ghi âm câu trả lời Speaking Part 2 hoặc luyện cùng bạn học. Dùng bảng mô tả band điểm để nhận xét độ trôi chảy, từ vựng, ngữ pháp và phát âm.

## Duy trì tiến độ

Trước tiên, xác định rõ bạn thi Academic hay General Training và thi trên giấy hay máy tính. Làm một bài thi thử để biết điểm mạnh, điểm yếu rồi xây dựng lịch học đều đặn. Thành công phụ thuộc vào nguồn học đáng tin cậy và sự kiên trì.""",
    },
    "https://takeielts.britishcouncil.org/prepare/ielts-academic/writing/tips-lexical-resources": {
        "title": "Mẹo nâng cao tiêu chí từ vựng trong IELTS Writing",
        "content_markdown": """# Mẹo cải thiện từ vựng trong IELTS Writing

Vốn từ là một trong bốn tiêu chí chấm IELTS Writing, bên cạnh ngữ pháp, tính mạch lạc và mức độ hoàn thành hoặc trả lời đề bài.

## Từ đồng nghĩa

Biết nhiều từ có nghĩa gần nhau giúp tránh lặp lại từ trong đề. Tuy nhiên, cần chú ý sắc thái và ngữ cảnh thay vì thay thế từ một cách máy móc.

## Kết hợp từ

Một số từ tiếng Anh thường xuất hiện cùng nhau thành các kết hợp tự nhiên. Ví dụ, người ta dùng “commit a crime” chứ không dùng “make a crime”. Hãy học từ theo cụm và ghi lại ngữ cảnh sử dụng; hiểu cách kết hợp từ sẽ giúp bài viết tự nhiên và chính xác hơn.

## Họ từ

Các từ như “economical”, “economic”, “economics” và “economy” thuộc cùng một họ nhưng có ý nghĩa và chức năng ngữ pháp khác nhau. Luyện dùng chúng trong câu giúp bạn chọn đúng dạng từ.

## Đọc và sửa bài

Dành vài phút cuối giờ để kiểm tra lỗi và thay một số từ quá phổ biến bằng từ phù hợp hơn. Không nên cố dùng từ khó khi chưa chắc về nghĩa hoặc cách kết hợp. Giám khảo quan tâm đến khả năng diễn đạt và phát triển ý rõ ràng, chính xác, chứ không chấm mức độ sáng tạo của quan điểm.""",
    },
    "https://takeielts.britishcouncil.org/teach-ielts/teaching-resources/videos/writing-task-achievement-response": {
        "title": "Mẹo dạy IELTS Writing: mức độ hoàn thành và trả lời yêu cầu đề bài",
        "content_markdown": """# Task Achievement và Task Response trong IELTS Writing

Tài liệu giải thích cấu trúc bài thi và cách giám khảo đánh giá Task 1, Task 2 theo bốn yếu tố:

- Mức độ hoàn thành yêu cầu ở Task 1 hoặc mức độ trả lời đề ở Task 2.
- Tính mạch lạc và liên kết giữa các ý.
- Phạm vi và độ chính xác của từ vựng.
- Độ đa dạng và chính xác của ngữ pháp.

Task Achievement xem xét thí sinh có trình bày đầy đủ, chính xác và phù hợp những thông tin Task 1 yêu cầu hay không. Task Response đánh giá việc trả lời tất cả các phần của câu hỏi, đưa ra lập trường rõ ràng và phát triển ý bằng lý do hoặc ví dụ trong Task 2.

Để cải thiện kết quả, người học cần phân tích kỹ đề, chỉ chọn thông tin hoặc luận điểm liên quan, tổ chức ý logic và dành thời gian kiểm tra ngôn ngữ. Giáo viên có thể sử dụng bảng mô tả band điểm để chỉ ra đặc điểm hiện tại của bài viết và mục tiêu cụ thể cần đạt ở band tiếp theo.""",
    },
}

ARTICLE_URLS = list(VIETNAMESE_ARTICLES)


class ArticleParser(HTMLParser):
    """Extract readable page content and preserve basic Markdown structure."""

    SKIPPED_TAGS = {"script", "style", "nav", "header", "footer", "aside", "svg", "form", "noscript"}
    BLOCK_TAGS = {"p", "div", "section", "blockquote", "table", "tr", "ul", "ol"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.body_depth = 0
        self.main_depth = 0
        self.skip_depth = 0
        self.title_depth = 0
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.main_parts: list[str] = []

    def _append(self, value: str) -> None:
        if self.skip_depth:
            return
        if self.body_depth:
            self.body_parts.append(value)
        if self.main_depth:
            self.main_parts.append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.title_depth += 1
        if tag == "body":
            self.body_depth += 1
        if tag in {"main", "article"}:
            self.main_depth += 1
        if tag in self.SKIPPED_TAGS:
            self.skip_depth += 1
            return
        if tag in self.BLOCK_TAGS:
            self._append("\n\n")
        elif tag in {"br", "hr"}:
            self._append("\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._append(f"\n\n{'#' * int(tag[1])} ")
        elif tag == "li":
            self._append("\n- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIPPED_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag in self.BLOCK_TAGS or tag in {"li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._append("\n")
        if tag in {"main", "article"}:
            self.main_depth = max(0, self.main_depth - 1)
        if tag == "body":
            self.body_depth = max(0, self.body_depth - 1)
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self.title_depth:
            self.title_parts.append(text)
        self._append(f"{text} ")

    @staticmethod
    def clean(parts: list[str]) -> str:
        text = "".join(parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def markdown(self) -> str:
        main = self.clean(self.main_parts)
        return main if len(main) >= 200 else self.clean(self.body_parts)


def _fetch_article(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; IELTS-RAG-Collector/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=60) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")

    parser = ArticleParser()
    parser.feed(html)
    if not parser.title or len(parser.markdown) < 200:
        raise ValueError(f"Page did not contain enough article content: {url}")
    translated = VIETNAMESE_ARTICLES[url]
    return {
        "url": url,
        "title": translated["title"],
        "date_crawled": datetime.now().astimezone().isoformat(timespec="seconds"),
        "content_markdown": translated["content_markdown"],
    }


async def crawl_article(url: str) -> dict:
    """Download one public article without blocking the asyncio event loop."""
    return await asyncio.to_thread(_fetch_article, url)


async def crawl_all() -> None:
    """Crawl và lưu từng bài thành một file JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    results = await asyncio.gather(
        *(crawl_article(url) for url in ARTICLE_URLS), return_exceptions=True
    )
    for index, (url, article) in enumerate(zip(ARTICLE_URLS, results), 1):
        if isinstance(article, Exception):
            print(f"Failed: {url} — {article}")
            continue
        try:
            output = DATA_DIR / f"article_{index:02d}.json"
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved: {output}")
        except Exception as error:
            print(f"Failed: {url} — {error}")


if __name__ == "__main__":
    asyncio.run(crawl_all())
