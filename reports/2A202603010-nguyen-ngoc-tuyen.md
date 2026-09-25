# Individual contribution report — Nguyễn Ngọc Tuyền

## Thông tin

- Họ và tên: Nguyễn Ngọc Tuyền
- Mã học viên: 2A202603010
- Nhóm: [Điền tên hoặc số nhóm]
- Vai trò chính: Giao diện và evaluation data
- Repository/branch: `K4-L3B-RAG-Pipeline` / `main`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Giao diện chatbot | Xây dựng/hoàn thiện giao diện Streamlit, lịch sử chat, lựa chọn top-k và hiển thị nguồn | `app.py` | Done — cần xác minh end-to-end sau indexing |
| Hiển thị citation | Hiển thị nhãn `[S1]`, title, URL/file, retrieval method, score, chunk index và excerpt | `app.py` | Done |
| Golden dataset | Xây dựng 18 câu hỏi, expected answer và expected context dựa trên corpus | `group_project/evaluation/golden_dataset.json`, commit `c608908` (được push bằng tài khoản Hoàng Phong; cần giải thích nếu nhóm dùng chung máy) | Done |
| Evaluation report | Chuẩn bị báo cáo 4 metrics, so sánh dense-only với hybrid + RRF và phân tích lỗi | `group_project/evaluation/RESULT.md` | Partial — chờ kết quả evaluation thật |
| Kiểm thử giao diện | Thử câu đúng domain, câu ngoài domain, citation và thao tác xóa lịch sử | [Điền ảnh/video hoặc mô tả test] | Partial |

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
- Query giao diện đã dùng: [Điền 2 câu đúng domain và 1 câu ngoài domain]
- Kết quả A/B cần điền: [Tên config tốt hơn và delta trung bình]
- Lỗi đã phát hiện và cách xử lý: [Điền lỗi UI/evaluation thực tế nếu có]

## Điều còn hạn chế

- Một hạn chế cụ thể: Các metric và worst performers chưa thể hoàn thiện trước khi ChromaDB index xong và evaluation runner chạy thành công.
- Nếu có thêm thời gian: Bổ sung câu hỏi khó/paraphrase, kiểm tra citation highlighting và phân tích lỗi theo retrieval/data/generation.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: [Điền ngày nộp]
- Tên thành viên: Nguyễn Ngọc Tuyền
