# Individual contribution report — Hoàng Phong

## Thông tin

- Họ và tên: Hoàng Phong
- Mã học viên: 2A202602943
- Nhóm: Nhóm như nào cũng được
- Vai trò chính: Data collection
- Repository/branch: `K4-L3B-RAG-Pipeline` / `main`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Thu thập văn bản pháp lý | Xây dựng Task 1 và thu thập 3 nghị định chính thức về đăng ký doanh nghiệp, thuế thương mại điện tử và hóa đơn điện tử | `src/task1_collect_legal_docs.py`, `data/landing/legal/`, commit `67f50f0`, `7a9ca53` | Done |
| Thu thập bài viết | Xây dựng Task 2 và thu thập 5 bài viết có URL, tiêu đề, ngày crawl và nội dung Markdown | `src/task2_crawl_news.py`, `data/landing/news/`, commit `67f50f0`, `7a9ca53` | Done |
| Kiểm tra dữ liệu đầu vào | Kiểm tra đủ số lượng file, định dạng PDF/JSON, metadata bắt buộc và sự phù hợp với chủ đề | `tests/test_acceptance.py` | Done |
| Hỗ trợ chuẩn hóa dữ liệu | Phối hợp kiểm tra nội dung sau OCR/convert, đặc biệt các đoạn dùng trong golden dataset | `data/standardized/legal/`, `data/standardized/news/`, `evaluation_results.json` | Done — corpus đã index và được đánh giá trên 18 câu |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Chọn corpus tiếng Việt về hộ kinh doanh, thuế thương mại điện tử và hóa đơn điện tử.  
   **Lý do/evidence:** Ba nghị định và năm bài viết cùng tập trung vào một miền kiến thức, giúp câu hỏi retrieval có phạm vi rõ ràng.  
   **Trade-off:** Phạm vi hẹp giúp tăng độ chính xác nhưng chatbot không phù hợp với câu hỏi pháp lý ngoài chủ đề.

2. **Quyết định:** Lưu dữ liệu gốc trong `data/landing/` và giữ metadata nguồn trước khi chuẩn hóa.  
   **Lý do/evidence:** URL, tiêu đề và filename được truyền sang pipeline để hiển thị citation.  
   **Trade-off:** PDF ký số là bản scan nên cần thêm bước OCR, có khả năng phát sinh lỗi nhận dạng dấu tiếng Việt.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng: `python -m pytest tests/test_acceptance.py -q -k "corpus_has_required"`
- Kết quả: Đủ 3 tài liệu legal và 5 bài news có metadata bắt buộc.
- Lỗi đã phát hiện và cách xử lý: PDF chính thức không có text layer; nhóm bổ sung OCRmyPDF/Tesseract trước khi convert Markdown.
- Bằng chứng bổ sung: corpus được index thành 1.425 chunks; acceptance test xác nhận đủ 3 legal, 5 news và 18 golden cases; raw evidence nằm trong `group_project/evaluation/evaluation_results.json`.

## Điều còn hạn chế

- Một hạn chế cụ thể: Nội dung OCR còn một số lỗi chính tả và dấu tiếng Việt, có thể ảnh hưởng BM25/context precision.
- Nếu có thêm thời gian: Rà soát và sửa các đoạn legal liên quan trực tiếp đến 18 câu trong golden dataset.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 25/09/2026
- Tên thành viên: Hoàng Phong

<!-- evaluation-results:start -->
## Kết quả evaluation liên quan phần việc data

Evaluation ngày 2026-09-25T13:45:40+07:00: dense-only average **0.8950**, hybrid + RRF average **0.9280** (delta **+0.0330**).

- Corpus đã chuẩn hóa gồm 3 legal + 5 news và được index thành 1.425 chunks.
- Ba worst performers và source IDs được lưu trong `evaluation_summary.json`;
  đây là bằng chứng để rà soát lỗi OCR/nội dung nguồn.
<!-- evaluation-results:end -->
