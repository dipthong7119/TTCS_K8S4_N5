# Kết quả kiểm thử T-27 / SCRUM-126 — Test dừng trụ ảo rồi bật lại, trạng thái đi đúng hai chiều

**Người thực hiện:** Hoàng Văn Đức (Tester Sprint 2)  
**Ngày thực hiện:** 2026-10-04  
**Trạng thái:** ✅ Completed (8/8 test cases PASS)  
**Môi trường:** Docker Compose (`csms_app`, `csms_db`)

---

## 1. Tóm tắt kết quả

| Mã TC | Tên ca kiểm thử | Mức độ | Kết quả | Ghi chú |
| :--- | :--- | :---: | :---: | :--- |
| **TC-126-01** | Trụ online → dừng → trạng thái chuyển offline | P0 | ✅ PASS | Trụ stale sau 2 chu kỳ heartbeat (`timeout = 10s`) tự động chuyển `offline`, `last_seen_at` được giữ nguyên. |
| **TC-126-02** | Connector chuyển về `unknown` khi trụ stale | P0 | ✅ PASS | Khi trụ stale, toàn bộ connector của trụ chuyển về `unknown`. |
| **TC-126-03** | Bật lại trụ → trạng thái trở về online | P0 | ✅ PASS | Nhận Heartbeat từ trụ hồi phục `status = online`, cập nhật `last_seen_at` mới. |
| **TC-126-04** | Connector trở về `available` sau khi trụ online lại | P1 | ✅ PASS | Nhận `StatusNotification` (Available), connector cập nhật từ `unknown` sang `rảnh`. |
| **TC-126-05** | Job không đánh dấu sai trụ vẫn đang online | P0 | ✅ PASS | Trụ hết hạn chuyển offline, trụ gửi heartbeat đều đặn vẫn giữ `online`. |
| **TC-126-06** | Lần chạy job lặp lại là no-op (idempotent) | P1 | ✅ PASS | Lần chạy thứ 2 trả về 0 bản ghi, không gây tác dụng phụ hoặc lỗi exception. |
| **TC-126-07** | SSE event được phát khi trụ chuyển offline | P1 | ✅ PASS | `notify_status_change` được kích hoạt gửi snapshot trạng thái tới client SSE. |
| **TC-126-08** | Bật/dừng nhiều trụ cùng lúc | P1 | ✅ PASS | Đồng thời xử lý nhiều trụ stale và online chính xác, không nhầm lẫn. |

---

## 2. Kết luận
Task **SCRUM-126 (T-27)** đã đáp ứng đầy đủ Acceptance Criteria của Story **S-12**:
- Trạng thái 2 chiều (Online ↔ Offline) hoạt động chuẩn xác theo thời gian thực.
- Trạng thái các đầu nối chuyển sang `unknown` khi trụ ngoại tuyến và hồi phục khi nhận `StatusNotification`.
- Toàn bộ 8/8 kịch bản kiểm thử đã được chạy thực nghiệm và vượt qua thành công.
