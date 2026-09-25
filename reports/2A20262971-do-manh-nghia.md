# Individual contribution report — Đỗ Mạnh Nghĩa

## Thông tin

- Họ và tên: Đỗ Mạnh Nghĩa
- Mã học viên: 2A20262971
- Nhóm: [Điền tên hoặc số nhóm]
- Vai trò chính: RAG pipeline
- Repository/branch: `K4-L3B-RAG-Pipeline` / `main`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Chuẩn hóa và OCR | Convert PDF/JSON sang Markdown có metadata; bổ sung OCR fallback cho PDF scan | `src/task3_convert_markdown.py`, `pyproject.toml` | Done |
| Chunking và indexing | Load Markdown, chia chunk có ID ổn định, embedding và upsert vào ChromaDB | `src/task4_chunking_indexing.py` | Partial — chờ ghi kết quả số chunk/index cuối |
| Dense và lexical retrieval | Xây dựng semantic search và BM25 trên cùng corpus | `src/task5_semantic_search.py`, `src/task6_lexical_search.py` | Done |
| RRF và fallback | Gộp bảng xếp hạng bằng RRF; dùng dense cosine score để quyết định PageIndex fallback | `src/task7_reranking.py`, `src/task8_pageindex_vectorless.py`, `src/task9_retrieval_pipeline.py` | Done — cần kiểm thử API thật nếu dùng PageIndex |
| Generation có citation | Tạo context, reorder evidence, gọi LLM và kiểm tra citation map với sources | `src/task10_generation.py` | Done — cần ghi kết quả query end-to-end |
| Kiểm thử pipeline | Bổ sung/duy trì contract và offline tests cho các luồng chính và lỗi provider | `tests/test_contracts.py`, `tests/test_offline_pipeline.py` | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Dense và BM25 dùng chung corpus chunk, sau đó chỉ fuse một lần bằng Reciprocal Rank Fusion.  
   **Lý do/evidence:** Tránh lệch dữ liệu giữa hai retriever và không trộn trực tiếp hai thang điểm không tương thích.  
   **Trade-off:** RRF cải thiện độ ổn định thứ hạng nhưng score của RRF không còn mang ý nghĩa cosine similarity.

2. **Quyết định:** Quyết định fallback bằng cosine score gốc của dense retrieval, không dùng RRF score.  
   **Lý do/evidence:** Dense score có ngưỡng diễn giải được; RRF score phụ thuộc thứ hạng và số danh sách đầu vào.  
   **Trade-off:** Cần hiệu chỉnh `SCORE_THRESHOLD` trên cả câu in-domain và out-of-domain.

## Kiểm thử và kết quả

- Test đã dùng: `python -m pytest tests/test_contracts.py tests/test_offline_pipeline.py -q`
- Kết quả gần nhất: Contract/offline pipeline pass; standardized legal/news và golden dataset cũng đã qua acceptance test.
- Kết quả indexing cần điền: `[Indexed ... chunks from 8 documents]`
- Query kiểm thử cần điền: [Một câu dense, một câu hybrid và một câu ngoài domain]
- Lỗi đã phát hiện và cách xử lý: MarkItDown trả nội dung rỗng vì 3 PDF là bản scan; bổ sung OCRmyPDF + Tesseract tiếng Việt và cache OCR trong `data/_tmp_pdf/`.

## Điều còn hạn chế

- Một hạn chế cụ thể: Chất lượng retrieval phụ thuộc lỗi OCR và threshold chưa được hiệu chỉnh bằng kết quả thực nghiệm đầy đủ.
- Nếu có thêm thời gian: Làm sạch OCR, đo latency và tuning chunk size/overlap/top-k trên golden dataset.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: [Điền ngày nộp]
- Tên thành viên: Đỗ Mạnh Nghĩa
