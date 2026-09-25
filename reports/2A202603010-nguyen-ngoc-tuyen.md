# Individual contribution report — Nguyễn Ngọc Tuyền

## Thông tin

- Họ và tên: Nguyễn Ngọc Tuyền
- Mã học viên: 2A202603010
- Nhóm: Nhóm như nào cũng được
- Vai trò chính: Giao diện và evaluation data
- Repository/branch: `K4-L3B-RAG-Pipeline` / `main`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Giao diện chatbot | Xây dựng/hoàn thiện giao diện Streamlit, lịch sử chat, lựa chọn top-k và hiển thị nguồn | `app.py` | Done — pipeline đã index; cần lưu thêm ảnh/video browser demo nếu giảng viên yêu cầu |
| Hiển thị citation | Hiển thị nhãn `[S1]`, title, URL/file, retrieval method, score, chunk index và excerpt | `app.py` | Done |
| Golden dataset | Xây dựng 18 câu hỏi, expected answer và expected context dựa trên corpus | `group_project/evaluation/golden_dataset.json`, commit `c608908` (được push bằng tài khoản Hoàng Phong; cần giải thích nếu nhóm dùng chung máy) | Done |
| Evaluation report | Chuẩn bị báo cáo 4 metrics, so sánh dense-only với hybrid + RRF và phân tích lỗi | `group_project/evaluation/RESULT.md`, `evaluation_results.json`, `evaluation_summary.json` | Done — đủ 36 records và 4 metrics |
| Kiểm thử giao diện | Pipeline đã kiểm thử 18 câu đúng domain ở cả hai cấu hình; UI có render answer/sources và thao tác xóa lịch sử | `app.py`, `evaluation_results.json` | Partial — chưa có ảnh/video browser demo trong repo |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Giao diện luôn hiển thị evidence và metadata nguồn cùng câu trả lời.  
   **Lý do/evidence:** Người dùng có thể đối chiếu citation với đoạn tài liệu thực tế thay vì chỉ nhận câu trả lời từ LLM.  
   **Trade-off:** Hiển thị toàn bộ nguồn có thể làm UI dài, nên đặt trong expander và giới hạn excerpt.

2. **Quyết định:** Dùng cùng 18 golden cases cho cả dense-only và hybrid + RRF.  
   **Lý do/evidence:** Bảo đảm A/B chỉ thay retrieval strategy, giữ nguyên generator, evaluator, prompt và `top_k`.  
   **Trade-off:** Golden dataset nhỏ, chủ yếu cùng một domain nên kết quả chưa đại diện cho mọi dạng câu hỏi pháp lý.

## Kiểm thử và kết quả

- Test golden dataset: `python -m pytest tests/test_acceptance.py -q -k golden_dataset`
- Kết quả: 18 cases, đủ `question`, `expected_answer`, `expected_context`, không có câu hỏi trùng.
- Query end-to-end tiêu biểu: “Nghị định 168/2025/NĐ-CP có hiệu lực từ ngày nào?”, “Sàn thương mại điện tử có chức năng thanh toán thực hiện nghĩa vụ thuế nào?” và “Bộ tài liệu thuế hướng dẫn riêng cho những nhóm đối tượng nào?”.
- Kết quả A/B: Config B — hybrid + RRF tốt hơn, average `0.9280` so với dense-only `0.8950`, delta `+0.0330`; hybrid thắng 7 câu, dense thắng 6, hòa 5.
- Lỗi đã phát hiện và cách xử lý: Gemini từng ngắt kết nối trong lúc Ragas chấm; runner được bổ sung checkpoint, retry 30/60/120 giây, disk cache và giới hạn 10 request/phút.

## Điều còn hạn chế

- Một hạn chế cụ thể: Golden dataset chỉ có 18 câu cùng domain; generator và evaluator dùng cùng Gemini model nên có thể có self-evaluation bias. UI vẫn cần bằng chứng browser demo thủ công.
- Nếu có thêm thời gian: Bổ sung câu hỏi khó/paraphrase, kiểm tra citation highlighting và phân tích lỗi theo retrieval/data/generation.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 25/09/2026
- Tên thành viên: Nguyễn Ngọc Tuyền

<!-- evaluation-results:start -->
## Kết quả evaluation liên quan UI và golden dataset

Evaluation ngày 2026-09-25T13:45:40+07:00: dense-only average **0.8950**, hybrid + RRF average **0.9280** (delta **+0.0330**).

- Đã đánh giá đủ 18 golden cases cho cả hai config.
- Cấu hình tốt hơn theo average: **Config B — hybrid + RRF**.
- Điểm từng metric, worst performers và khuyến nghị đã được ghi tự động vào
  `group_project/evaluation/RESULT.md`.
<!-- evaluation-results:end -->
