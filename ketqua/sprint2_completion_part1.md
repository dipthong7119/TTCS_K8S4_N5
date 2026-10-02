# Sprint 2 — OCPP, xác thực và trạng thái đầu nối

## Phần đã triển khai

- **S-06 / T-12–T-13:** WebSocket `/ocpp/{charge_point_code}`, thương lượng `ocpp1.6`, tra mã trụ, từ chối mã lạ và ghi cảnh báo một lần.
- **S-07 / T-14–T-15:** parser/packer độc lập cho `CALL`, `CALLRESULT`, `CALLERROR`; khung sai và hành động chưa hỗ trợ trả đúng loại lỗi OCPP để kết nối còn mở.
- **S-08 / T-16–T-17:** `BootNotification` lưu hãng, model, firmware; trả thời gian UTC và chu kỳ heartbeat cấu hình được. Trạm `inactive` vẫn cho trụ kết nối; trạm `locked` do quản trị viên khóa bị trả `Rejected`. Trụ chưa Boot thành công không được gửi các CALL nghiệp vụ khác.
- **S-09 / T-18:** cập nhật `last_seen_at` bằng thời gian máy chủ khi nhận tin nhắn và trả giờ UTC trong `Heartbeat`.
- **S-10 / T-20–T-22:** ánh xạ trạng thái OCPP, lưu nguyên trạng thái lạ riêng, ghi lịch sử lỗi đầu nối, bỏ qua đầu nối chưa khai báo và phát cảnh báo.

## Trạng thái xác nhận

Các handler và quy tắc trên có test cục bộ. Các bài chạy simulator giữ WebSocket 10 phút, chạy 20 thiết bị trên staging và đối chiếu độ trễ vẫn cần môi trường simulator/staging; vì vậy trạng thái story tương ứng trong bản workbook rà soát vẫn là `In Progress`.
