# Kết quả nghiệm thu T-24 (SCRUM-124) — Lưới giám sát trụ

**Trạng thái:** HOÀN THÀNH TOÀN DIỆN (Đạt đầy đủ tiêu chí Giai đoạn 1 & Giai đoạn 2)

### Các tiêu chí nghiệm thu đã hoàn tất:
1. **Bố cục lưới & co giãn (AC T-24):**
   - Đã tích hợp bộ dữ liệu mẫu 20 trụ (`CP-HN-01` đến `CP-HN-20`) phân bổ qua 4 trạm.
   - Xác nhận trực quan toàn bộ bố cục hiển thị vừa vặn trên màn hình desktop chuẩn mà không bị cuộn ngang.
   - Hỗ trợ chuyển đổi linh hoạt giữa chế độ xem lưới (Grid) và danh sách (List).

2. **Phân biệt trạng thái & Hỗ trợ người mù màu (Accessibility):**
   - Mọi trạng thái hiển thị bằng nhãn chữ tiếng Việt đi kèm màu sắc và chỉ báo trực quan rõ nét (không phụ thuộc duy nhất vào màu sắc).
   - Khối chú giải trạng thái (Status Legend) hiển thị ngay đầu trang hỗ trợ nhận biết trực quan: Sẵn sàng, Đang sạc, Đã đặt chỗ / Tạm dừng, Ngoại tuyến / Tạm ngừng, Báo lỗi, Chưa rõ.

3. **Thông tin liên lạc cuối (Last Seen At):**
   - Với trụ ngoại tuyến, hiển thị rõ ràng thời điểm liên lạc cuối (`last_seen_at`) theo định dạng thời gian địa phương (`vi-VN`).

4. **Ghép nối API máy chủ thật (SCRUM-122 / Giai đoạn 2):**
   - Tích hợp chuẩn qua `ApiClient.getMonitoringTree()` gọi endpoint `GET /api/monitoring/tree`.
   - Eager-load trạm – trụ – đầu nối một lần truy vấn, tự động thích ứng theo vai trò người dùng (Admin, Operator, Station Owner).
   - Cơ chế tự động fallback sang dữ liệu mẫu 20 trụ khi máy chủ chưa khởi tạo dữ liệu hoặc gặp lỗi kết nối.

5. **Đồng bộ thời gian thực SSE (SCRUM-123 / T-25):**
   - Kết nối trực tiếp luồng Server-Sent Events tại `/api/monitoring/sse` qua `SseClient`.
   - Lắng nghe sự kiện `status_update` cập nhật trạng thái trụ và đầu nối tức thì (dưới 1 giây theo AC T-25).
   - Đồng bộ thời gian thực ngay cả khi đang mở Drawer chi tiết trạm (live detail updates) mà không cần đóng mở lại.
   - Tự động khôi phục kết nối và nạp lại trạng thái chuẩn (authoritative tree) khi máy chủ khởi động lại hoặc mạng phục hồi.

6. **Tích hợp nút điều khiển khởi động lại (SCRUM-134):**
   - Tích hợp `RestartButton` của Tú trên giao diện chi tiết từng trụ, kiểm tra quyền điều khiển (`canReset`) và xử lý xác nhận trước khi gửi lệnh.

7. **Chế độ kiểm thử linh hoạt:**
   - Nút chuyển đổi *"Dữ liệu mẫu (20 trụ)"* / *"Dữ liệu máy chủ (API)"* hỗ trợ Tester và QA diễn tập kiểm thử nghiệm thu bất cứ lúc nào.


