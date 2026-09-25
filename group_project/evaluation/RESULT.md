# RAG evaluation results

## Run information

| Field | Value |
| ----- | ----- |
| Evaluation date | 2026-09-25T13:45:40+07:00 |
| Framework and version | ragas 0.4.3 |
| Evaluator model | Gemini `gemini-3.5-flash-lite`; temperature `0`; answer relevancy strictness `1` |
| Generator model | Gemini `gemini-3.5-flash-lite`; temperature `0.3`; top-p `0.9` |
| Embedding model | Sentence Transformers `BAAI/bge-m3` |
| Corpus | 3 legal documents + 5 news articles; 1,425 indexed chunks |
| Code/corpus commit at evaluation | `f5c23ae` |
| Golden dataset size | 18 |
| `top_k` | 5 |
| A/B fallback threshold | `-1.0` (fallback disabled to isolate retrieval strategy) |
| Gemini rate limit used | 10 requests/minute with checkpoint, retry and Ragas disk cache |

## Configurations

- **Config A — dense-only:** cosine search over ChromaDB; `use_reranking=False`.
- **Config B — hybrid + RRF:** dense + BM25, fused once with RRF `k=60`;
  `use_reranking=True`.

Hai config dùng cùng corpus, golden dataset, generator, evaluator, prompt và
`top_k`; chỉ thay retrieval strategy.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
| ------ | -------: | -------: | --------: |
| Faithfulness | 0.9352 | 0.9259 | -0.0093 |
| Answer relevance | 0.8901 | 0.9231 | +0.0330 |
| Context recall | 0.9167 | 0.9889 | +0.0722 |
| Context precision | 0.8383 | 0.8741 | +0.0358 |
| **Average** | **0.8950** | **0.9280** | **+0.0330** |

## A/B comparison

- Cấu hình tốt hơn theo average: **Config B — hybrid + RRF**.
- Evidence: delta average hybrid − dense là **+0.0330** trên
  18 câu; delta từng metric được trình bày trong
  bảng phía trên.
- Theo từng câu: hybrid thắng **7**, dense
  thắng **6**, hòa
  **5**.
- Latency generation trung bình: dense-only **8.92s**,
  hybrid + RRF **6.04s** mỗi câu.
- Latency median: dense-only **5.99s**,
  hybrid + RRF **6.10s**. Median cho thấy
  hybrid chậm hơn khoảng **0.11s**;
  mean của dense bị tăng bởi lần cold-start tải embedding model đầu tiên.
- Chi phí LLM generation tương đương vì mỗi config gọi generator một lần/câu;
  hybrid thêm chi phí tính toán BM25 + RRF cục bộ.
- Cả 36 outputs đều có citation hợp lệ; có **1**
  partial refusal và **0** answer thiếu citation.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| -: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------- | ---------- |
| 1 | Bộ tài liệu thuế cho thương mại điện tử hướng dẫn riêng cho những nhóm đối tượng nào? | dense_only | 0.6667 | 0.0000 | 0.0000 | 0.0000 | retrieval/data | Top-5 dense lấy đúng bài nhưng bỏ sót chunk chứa danh sách đối tượng; generator vì thế trả lời thiếu/partial refusal |
| 2 | Nghị định 168/2025/NĐ-CP điều chỉnh những nội dung nào liên quan đến hộ kinh doanh? | hybrid_rrf | 0.0000 | 0.9422 | 0.8000 | 0.3333 | generation | Context có passage liên quan nhưng bị trộn với chunk nhiễu/OCR; faithfulness judge cũng cần được kiểm tra vì answer có citation hỗ trợ |
| 3 | Nghị định 168/2025/NĐ-CP điều chỉnh những nội dung nào liên quan đến hộ kinh doanh? | dense_only | 0.1667 | 0.9602 | 0.5000 | 1.0000 | generation | Context có passage liên quan nhưng bị trộn với chunk nhiễu/OCR; faithfulness judge cũng cần được kiểm tra vì answer có citation hỗ trợ |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
| 1 | Rà soát/sửa OCR tại các passages của ba worst performers | Legal PDFs là bản scan và OCR còn lỗi dấu/từ | Tăng context recall và precision | Sửa corpus, re-index và chạy lại cùng runner |
| 2 | Tuning chunk size/overlap và `top_k` trên golden dataset | Worst performers chỉ ra câu bị thiếu hoặc thừa evidence | Cải thiện recall/precision | A/B cấu hình chunk mới, giữ nguyên generator/evaluator |
| 3 | Calibrate fallback trên tập in-domain/out-of-domain riêng | A/B này chủ động tắt fallback | Safe refusal và PageIndex ổn định hơn | Báo cáo score distribution và test ít nhất 5+5 câu |

## Limitations

- Golden dataset có 18 câu trong cùng một domain nên chưa đại diện cho mọi câu
  hỏi pháp lý hoặc câu hỏi đối kháng.
- Generator và evaluator dùng cùng model Gemini, có thể tạo self-evaluation bias.
- Answer relevancy dùng `strictness=1` để phù hợp giới hạn 15 request/phút;
  chạy nhiều lần hoặc strictness cao hơn có thể giảm variance.
- Các PDF legal là bản scan OCR và vẫn còn lỗi dấu/từ. Q2 cho thấy
  faithfulness judge có thể cho điểm thấp dù answer có passage/citation hỗ trợ,
  vì vậy worst cases đã được kiểm tra thủ công thay vì chỉ đọc metric.
- Fallback/PageIndex không thuộc A/B này (`score_threshold=-1.0`) và chưa có
  kết quả calibration thực nghiệm.

## Reproducibility artifacts

- `group_project/evaluation/golden_dataset.json`: 18 reference cases.
- `group_project/evaluation/evaluation_results.json`: answer, contexts, source IDs,
  latency và metric theo từng câu/config.
- `group_project/evaluation/evaluation_summary.json`: aggregate scores, delta và
  worst performers.
- Chạy lại: `python -m group_project.evaluation.run_evaluation --rpm 10`.
