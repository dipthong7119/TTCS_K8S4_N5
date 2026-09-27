# Kết quả rà soát T-17 — Khoảng nhịp tim cấu hình được

**Trạng thái:** In Progress

- BootNotification dùng OCPP_HEARTBEAT_INTERVAL_SECONDS để trả interval; test cục bộ xác nhận đổi cấu hình thì giá trị trả về đổi.
- Chưa khởi động lại tiến trình container với biến môi trường khác để xác nhận trên Docker vì Docker Engine không khả dụng.
