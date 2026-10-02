# Kết quả rà soát T-25 — SSE cập nhật trạng thái

**Trạng thái:** In Progress

- Backend gửi sự kiện theo owner_id; test mới xác nhận chủ trạm khác không nhận dữ liệu và operator nhận được sự kiện toàn cục.
- EventSource tự kết nối lại; frontend tải lại cây trạng thái khi mở/kết nối lại SSE.
- Chưa đo độ trễ dưới 1 giây hoặc thử tắt/bật server trên staging.
