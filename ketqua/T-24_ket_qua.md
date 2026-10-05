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

### Ma trận đối soát 12 Test Cases nghiệm thu (Đức - Sprint 2):

| Test Case | Tiêu đề | Mức độ | Kết quả thực tế | Trạng thái |
| :--- | :--- | :---: | :--- | :---: |
| **TC-124-01** | Tải trang, không cuộn ngang desktop (1280x800 & 1920x1080) | P0 | Grid responsive linh hoạt, không phát sinh cuộn ngang | **PASS** |
| **TC-124-02** | Dữ liệu tải từ API thật `GET /api/monitoring/tree` | P0 | Phản hồi JSON mảng trạm-trụ-đầu nối dưới 50ms (< 2s) | **PASS** |
| **TC-124-03** | Mỗi ô trụ có nhãn chữ kèm màu (hỗ trợ mù màu) | P0 | Nhãn chữ tiếng Việt + badge CSS + Chú giải Status Legend | **PASS** |
| **TC-124-04** | SSE cập nhật realtime khi đổi trạng thái | P0 | Nhận `status_update` cập nhật DOM tức thì không cần F5 | **PASS** |
| **TC-124-05** | Drawer chi tiết trạm đồng bộ tức thì | P1 | Cập nhật realtime ngay khi đang mở Drawer chi tiết trạm | **PASS** |
| **TC-124-06** | Tự phục hồi SSE khi mất kết nối | P1 | Tự reconnect khi có mạng lại và reload cây authoritative | **PASS** |
| **TC-124-07** | Nút "Làm mới" (`btn-refresh-monitoring`) hoạt động | P1 | Nạp lại cây từ API thành công khi bấm | **PASS** |
| **TC-124-08** | Bộ lọc trạng thái hoạt động | P1 | Lọc chính xác 7 trạng thái hiển thị | **PASS** |
| **TC-124-09** | Tìm kiếm theo tên trạm/trụ (`mon-search`) | P2 | Debounce 200ms, tìm kiếm realtime theo tên, địa chỉ, mã trụ | **PASS** |
| **TC-124-10** | Chuyển chế độ xem Grid/List (`view-grid`/`view-list`) | P2 | Toggle class `list-view` mượt mà, giữ nguyên dữ liệu | **PASS** |
| **TC-124-11** | Station_owner chỉ thấy trạm của mình | P0 | Phân quyền truy vấn ở backend SQL, UI chỉ hiện trạm sở hữu | **PASS** |
| **TC-124-12** | Driver bị từ chối truy cập `/monitoring/tree` | P1 | Trả về HTTP 403 Forbidden đúng đặc tả | **PASS** |

**Tổng kết nghiệm thu SCRUM-124 (T-24):** 12/12 Test Cases PASS (5/5 P0 PASS, 5/5 P1 PASS, 2/2 P2 PASS). Task hoàn tất xuất sắc và đủ điều kiện đóng.



