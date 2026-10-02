# Kết quả rà soát T-12 — WebSocket cho trụ đã đăng ký

**Trạng thái:** In Progress

- Endpoint OCPP tra mã trụ đã đăng ký, yêu cầu subprotocol ocpp1.6 và giữ kết nối tới khi trụ ngắt.
- Test cục bộ phủ kết nối hợp lệ, mã trụ lạ, subprotocol sai và trạm tạm ngừng.
- Chưa chạy kiểm tra giữ kết nối 10 phút hoặc 50 kết nối đồng thời trên staging vì Docker Engine/staging không khả dụng.
