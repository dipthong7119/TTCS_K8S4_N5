# Kết quả rà soát T-19 — Thời điểm liên lạc không phụ thuộc đồng hồ trụ

**Trạng thái:** In Progress

- Bổ sung test gửi Heartbeat có timestamp lệch 5 giờ; last_seen_at vẫn nằm trong 2 giây so với CURRENT_TIMESTAMP của SQLite trong test.
- Test mới và toàn suite đạt tại máy này. GitHub Actions chưa chạy lại sau thay đổi.
- Heartbeat chuẩn không mang timestamp; test cố ý đưa trường timestamp lệch vào để xác nhận máy chủ không dùng giờ do trụ gửi.
