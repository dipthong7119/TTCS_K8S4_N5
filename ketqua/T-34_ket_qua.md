# Kết quả rà soát T-34 — Gửi CALL và khớp CALLRESULT

**Trạng thái:** In Progress

- ConnectionManager sinh message ID, gửi Reset, ghép CALLRESULT theo mã và dọn lời gọi khi hết thời gian.
- Test cục bộ xác nhận phản hồi được ghép đúng và timeout xóa lời gọi đang chờ.
- Chưa chạy lệnh Reset với simulator thật qua WebSocket trong ứng dụng.
