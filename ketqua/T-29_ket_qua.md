# Kết quả rà soát T-29 — Thay kết nối trùng mã trụ

**Trạng thái:** In Progress

- ConnectionManager đóng socket cũ và thay bằng socket mới; log ghi mã trụ cùng định danh socket cũ/mới.
- Test cục bộ xác nhận socket cũ bị đóng, socket mới được giữ và log chỉ rõ cặp kết nối.
- Chưa chạy hai WebSocket thật đồng thời hoặc xác nhận workflow CI sau cập nhật.
