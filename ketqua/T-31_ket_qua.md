# Kết quả kiểm thử T-31 / SCRUM-130 — Test cleanup tin nhắn OCPP cũ & Idempotency lặp 5 lần

**Người thực hiện:** Hoàng Văn Đức (Tester Sprint 2)  
**Ngày thực hiện:** 2026-10-04  
**Trạng thái:** ✅ Completed (6/6 test cases PASS + Idempotency 5x PASS)  
**Môi trường:** Docker Compose (`csms_app`, `csms_db`)

---

## 1. Tóm tắt kết quả kiểm thử

| Mã TC | Tên ca kiểm thử | Mức độ | Kết quả | Ghi chú thực tế |
| :--- | :--- | :---: | :---: | :--- |
| **TC-130-01** | Bản ghi cũ hơn 7 ngày bị xóa | P0 | ✅ PASS | Bản ghi cũ hơn 8 ngày (`test-scrum130-old-001`) bị xóa hoàn toàn khỏi DB; hàm cleanup trả về số lượng xóa >= 1. |
| **TC-130-02** | Bản ghi trong 7 ngày KHÔNG bị xóa | P0 | ✅ PASS | Bản ghi tạo cách đây 3 ngày (`test-scrum130-new-001`) được bảo toàn nguyên vẹn trong DB sau khi chạy job cleanup. |
| **TC-130-03** | Bản ghi đúng 7 ngày (kiểm tra biên) | P1 | ✅ PASS | Xác nhận chuẩn xác: bản ghi `< cutoff` (cũ hơn 7 ngày 1 giờ) bị xóa; bản ghi `>= cutoff` (mới hơn 7 ngày 1 giờ) được giữ lại. |
| **TC-130-04** | Job chạy lại là no-op khi không còn bản ghi cũ | P1 | ✅ PASS | Lần chạy thứ 2 trả về đúng 0 bản ghi bị xóa, không phát sinh ngoại lệ hay tác dụng phụ. |
| **TC-130-05** | Xóa nhiều bản ghi cùng lúc (bulk delete 50 bản ghi) | P1 | ✅ PASS | Chèn 50 bản ghi cũ 10 ngày trước; hàm cleanup xóa trọn vẹn cả 50 bản ghi trong 1 transaction (return = 50), không có partial delete. |
| **TC-130-06** | Job async chạy theo chu kỳ, không crash | P1 | ✅ PASS | Coroutine async `cleanup_old_ocpp_messages` thực thi chu kỳ ổn định, xử lý `CancelledError` an toàn khi dừng ứng dụng. |
| **Idempotency** | Gửi lại cùng một CALL 5 lần liên tiếp | P0 | ✅ PASS | Gửi 1 lần gốc + 5 lần gửi lại với cùng `msg_id` và `charge_point_code`; cả 6 lần nhận đúng cached response; bảng `ocpp_messages` chỉ có đúng 1 bản ghi duy nhất. |

---

## 2. Kịch bản kiểm chứng tự động
- Script thực nghiệm trực tiếp: [`tests/test_scrum130_live.py`](file:///d:/TTCS_K8S4_N5/tests/test_scrum130_live.py)
- Toàn bộ suite unit tests backend liên quan (`test_ocpp_messages.py`, `test_jobs.py`): **136/136 unit tests passed**.

---

## 3. Kết luận nghiệm thu
Task **SCRUM-130 (T-31)** đã đáp ứng đầy đủ Acceptance Criteria của Story **S-14** & **SCRUM-50**:
1. Cơ chế dọn dẹp tin nhắn OCPP định kỳ xóa sạch dữ liệu quá thời hạn cấu hình (`OCPP_MESSAGE_RETENTION_DAYS = 7` ngày) và giữ nguyên vẹn các bản ghi hợp lệ.
2. Cơ chế khóa chống trùng tin nhắn (Idempotency) theo cặp `(charge_point_code, msg_id)` hoạt động chính xác tuyệt đối: các lần gửi lại được phản hồi ngay lập tức từ bộ nhớ đệm cơ sở dữ liệu mà không gây trùng lặp bản ghi hay xử lý lại nghiệp vụ.
