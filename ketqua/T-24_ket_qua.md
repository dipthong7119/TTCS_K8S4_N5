# Kết quả rà soát T-24 — Lưới giám sát trụ

**Trạng thái:** Đạt tiêu chí giai đoạn 1 (Mock 20 trụ & giao diện desktop); sẵn sàng ghép nối API thật (Giai đoạn 2)

- **Bố cục lưới & co giãn:** Đã tích hợp bộ dữ liệu mẫu 20 trụ (`CP-HN-01` đến `CP-HN-20`) phân bổ qua 4 trạm; xác nhận trực quan toàn bộ bố cục hiển thị vừa vặn trên màn hình desktop chuẩn mà không bị cuộn ngang.
- **Phân biệt trạng thái (Accessibility):** Trạng thái hiển thị bằng nhãn chữ tiếng Việt đi kèm màu sắc và chỉ báo trực quan rõ nét; đã bổ sung khối chú giải (Legend) ngay trên trang giúp người mù màu dễ dàng nhận biết (Sẵn sàng, Đang sạc, Đã đặt chỗ, Ngoại tuyến, Báo lỗi).
- **Trụ ngoại tuyến:** Hiển thị rõ ràng thời điểm liên lạc cuối (`last_seen_at`) theo định dạng địa phương.
- **Chế độ kiểm thử linh hoạt:** Hỗ trợ nút chuyển đổi dữ liệu mẫu 20 trụ và tự động fallback khi máy chủ chưa có dữ liệu hoặc API chưa sẵn sàng.

