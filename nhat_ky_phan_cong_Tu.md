# Nhật ký phân công công việc - Vy Hoàng Tú (Sprint 345)

**Thời gian cập nhật:** 09/10/2026
**Vai trò:** Frontend Developer (Mảng giao diện biểu giá, hoá đơn)

## 1. Danh sách nhiệm vụ hiện tại (Sprint 3)
- **SCRUM-61 (FE):** Màn hình khai báo biểu giá theo kWh và phí chiếm trụ (3 SP).
- **SCRUM-62 (FE):** Màn hình cấu hình nhiều khung giờ, cảnh báo chồng lấn/thiếu giờ (3 SP).
- **SCRUM-63 (Subtask FE: 208):** Hiển thị chi tiết cách tính tiền theo từng khung giờ cho phiên sạc (5 SP chung).
- **SCRUM-66 (FE):** Màn hình hoá đơn có diễn giải từng đoạn giá (3 SP).

*(Ghi chú: SCRUM-68 (FE) - Giao diện gói thuê bao đã được chuyển giao cho Phạm Văn Tuấn để giảm tải).*

## 2. Điều kiện bắt đầu làm việc (Dependencies)
Theo quy tắc chống nghẽn (Mục 6.1), Tú có thể bắt đầu làm việc ngay bằng cách sử dụng **Mock data** thay vì đợi Backend hoàn thành:

* **Đối với SCRUM-61, 62 (FE):** 
  - Đang chờ API biểu giá từ Hoàng Văn Tân và Trịnh Thanh Tùng.
  - **Hành động:** Chốt sớm hợp đồng API với Tân và Tùng, sau đó dùng dữ liệu giả (mock) để làm giao diện.
* **Đối với SCRUM-208, 66 (FE):** 
  - Đang chờ dữ liệu đoạn tính tiền (207, 66 BE) từ Tạ Như Vinh.
  - **Hành động:** Chốt sớm format hoá đơn với Vinh, sau đó sử dụng dữ liệu mock để tiếp tục công việc.

## 3. Hoạt động kiểm thử / Review chéo
- Nhận review/test từ: **Đặng Ngọc Đại**
- Người Tú cần review code: **Phạm Văn Tuấn** (đảm bảo review trong ngày khi có PR mở).

## 4. Ghi chú cá nhân
- Luôn ưu tiên chốt schema/hợp đồng API ngay từ đầu Sprint.
- Nếu bị chờ BE quá 1 ngày (dù đã hối thúc), báo cáo ngay cho Scrum Master (Trịnh Thanh Tùng) trong buổi Daily Scrum.

## 5. Tiến độ thực hiện (Cập nhật ngày 11/10/2026)
- **[HOÀN THÀNH 100%] SCRUM-61 (FE - Khai báo biểu giá theo kWh và phí chiếm trụ theo phút):**
  - Tích hợp trực tiếp vào màn hình sửa trạm sạc (`frontend/templates/stations/form.html` và `frontend/static/js/pages/stations_form.js`).
  - Hỗ trợ đầy đủ các trường: Tên biểu giá, Đơn giá điện (hoặc chế độ nhiều khung giờ), Phí chiếm trụ (đồng/phút), Thời gian ân hạn (phút), Thời điểm hiệu lực (`effective_from`).
  - Kết nối API authoritative `POST /api/stations/{station_id}/tariffs` và `GET /api/stations/{station_id}/tariffs`.
  - Hiển thị danh sách lịch sử các phiên bản biểu giá của trạm với đầy đủ thông tin phí và thời điểm áp dụng.
- **[HOÀN THÀNH 100%] SCRUM-62 (FE - Cấu hình nhiều khung giờ, cảnh báo chồng lấn/thiếu giờ):**
  - Thiết kế tab chuyển đổi trực quan giữa 2 chế độ: "Đơn giá cố định cả ngày" và "Nhiều khung giờ (Time-of-Use)".
  - Hỗ trợ thêm/xóa/sửa các khung giờ động linh hoạt trong ngày.
  - Tích hợp nút tiện ích: "⚡ Áp dụng mẫu 24h chuẩn" nạp nhanh 3 khung giờ mẫu (Thấp điểm, Tiêu chuẩn, Cao điểm).
  - Thanh trực quan 24 giờ (Visual 24-hour timeline bar) chia tỉ lệ theo 1440 phút, phân màu rõ rệt theo loại khung giờ và hiển thị các khoảng hở (gaps) hoặc chồng lấn (overlaps).
  - Thuật toán kiểm tra (Client-side validation) thời gian thực theo đúng chuẩn nghiệp vụ:
    - Bắt lỗi hở giờ chính xác đến từng phút (`Biểu giá bị hở từ XX:XX đến YY:YY` hoặc `đến 24:00`).
    - Bắt lỗi chồng lấn giờ chính xác (`Biểu giá bị chồng lấn từ XX:XX đến YY:YY`).
    - Bắt lỗi giờ trùng nhau, đơn giá âm, tên khung rỗng.
    - Hiển thị thông báo trạng thái màu xanh khi cấu hình hợp lệ phủ kín 24h.
  - Chuyển đổi dữ liệu sang định dạng `bands: [{label, start_minute, end_minute, price_vnd_per_kwh}]` gửi lên API Backend.
  - Thẻ lịch sử biểu giá hiển thị chi tiết từng khung giờ kèm dải thời gian và đơn giá.
- **Bước tiếp theo:**
  - Chuyển sang thực hiện **SCRUM-63 (Subtask 208 FE)** và **SCRUM-66 (FE)**: Nâng cấp bảng chi tiết diễn giải hóa đơn (Breakdown segments) trên trang phiên sạc `my_session.html` / `my_session.js`.
