# Kết quả thực hiện SCRUM-76 — Màn hình đặt chỗ trụ sạc cho tài xế

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)  
**Vai trò:** Frontend Developer (Sprint 6-7-8)  
**Epic:** Đặt chỗ trụ sạc (E-07)  
**Story:** SCRUM-76 (S-48: Tài xế đặt chỗ một trụ trong khoảng thời gian — 5 SP)  
**Người phối hợp Backend:** Ngô Quang Tùng / Nguyễn Lâm Tùng  
**Reviewer:** Trịnh Thanh Tùng (Scrum Master) / Vy Hoàng Tú (FE)  
**Trạng thái:** Hoàn tất 100% triển khai Frontend, Tích hợp UI/UX và Hợp đồng API Mock  

---

### 1. Mục tiêu và Tiêu chí nghiệm thu (Acceptance Criteria)

- **Mục tiêu:** Cung cấp cho tài xế giao diện trực quan để đặt trước vị trí trụ sạc trong vòng 2 giờ tới, giúp tài xế chủ động lộ trình di chuyển mà không lo hết trụ khi đến nơi. Khi đặt chỗ thành công, hệ thống gửi lệnh `ReserveNow` khóa trụ sạc, đầu nối hiển thị trạng thái `Reserved` và đồng hồ đếm ngược thời gian giữ chỗ kích hoạt ngay lập tức.
- **Tiêu chí nghiệm thu (theo đặc tả S-48 / SCRUM-76):**
  1. **Chọn trụ và thời gian tới trong vòng 2 giờ:**
     - Cho phép tài xế chọn trạm sạc và chỉ hiển thị các đầu nối đang ở trạng thái `Sẵn sàng (Available)`.
     - Bộ nút chọn nhanh thời gian giữ chỗ linh hoạt: 15 phút, 30 phút, 45 phút, 1 giờ, 1.5 giờ, 2 giờ (tối đa theo spec).
     - Hiển thị mốc thời gian hết hạn cụ thể (`HH:MM, hôm nay`).
  2. **Gửi lệnh đặt chỗ và khóa trụ (`ReserveNow`):**
     - Gửi yêu cầu đặt chỗ tới máy chủ CSMS.
     - Khi nhận kết quả thành công (`Accepted`): chuyển trụ/đầu nối sang trạng thái `Reserved` (Đã đặt chỗ).
     - Tự động kích hoạt Thẻ đặt chỗ hiệu lực (Hero Card) với **đồng hồ đếm ngược thời gian thực (Countdown Timer)**.
  3. **Xử lý phản hồi khi trụ bận hoặc từ chối:**
     - Khi trụ trả `Occupied` (HTTP 409): hiển thị cảnh báo rõ ràng trụ/đầu nối đang bận hoặc vừa có người đặt trước, gợi ý chọn đầu nối khác (tiền đề chống tranh chấp SCRUM-77).
     - Khi trụ trả `Rejected` (HTTP 502): thông báo trụ từ chối lệnh ReserveNow và gợi ý thử lại.
  4. **Quản lý danh sách lịch sử đặt chỗ:**
     - Thống kê 4 chỉ số: Đang giữ chỗ (Active), Đã hoàn thành (Completed), Đã hủy (Cancelled), Quá hạn (Expired).
     - Bảng tra cứu lịch sử đầy đủ: Mã đặt chỗ `#RES-...`, Trạm sạc, Trụ & Cổng, Thời điểm đặt, Hạn giữ chỗ, Trạng thái (badge màu tương phản cao), Thao tác xem chi tiết.
     - Thanh tìm kiếm từ khóa thời gian thực và bộ lọc theo trạng thái.
  5. **Tích hợp liên kết trải nghiệm người dùng liền mạch:**
     - Thêm mục "Đặt chỗ của tôi" trên menu sidebar `base.html` dành riêng cho vai trò tài xế (`driver`).
     - Tích hợp nút "Đặt trước trụ này" trực tiếp trong Drawer chi tiết trụ sạc tại trang Giám sát `/monitoring` và trang danh sách trạm `/stations`.
     - Tự động điền trước thông tin trạm và trụ khi chuyển hướng với tham số URL `?action=reserve&cp_code=...`.

---

### 2. Hợp đồng API bàn giao Backend (Ngô Quang Tùng & Nguyễn Lâm Tùng)

#### 2.1. API Tạo đặt chỗ mới
* **Endpoint:** `POST /api/reservations`
* **Quyền hạn:** `driver`
* **Request Body:**
```json
{
  "charge_point_code": "CP_VINCOM_01",
  "connector_id": 1,
  "arrival_minutes": 30,
  "expiry_at": "2026-10-14T12:30:00Z"
}
```
* **Response Thành công (HTTP 201 Created / 200 OK):**
```json
{
  "id": 105,
  "reservation_code": "RES-20261014-005",
  "charge_point_code": "CP_VINCOM_01",
  "connector_id": 1,
  "station_id": 1,
  "station_name": "Trạm Sạc Vincom Bà Triệu",
  "station_address": "191 Bà Triệu, Hai Bà Trưng, Hà Nội",
  "status": "Active",
  "ocpp_status": "Accepted",
  "created_at": "2026-10-14T12:00:00Z",
  "expiry_at": "2026-10-14T12:30:00Z",
  "arrival_minutes": 30,
  "message": "Đặt chỗ thành công! Trụ sạc đã được khóa cho bạn trong 30 phút."
}
```
* **Response Thất bại (HTTP 409 Conflict - Trụ bận/đã có người đặt):**
```json
{
  "status": 409,
  "detail": "Trụ sạc hoặc đầu nối này hiện đang bận hoặc vừa có người đặt trước. Vui lòng chọn đầu nối khác.",
  "code": "connector_occupied"
}
```
* **Response Thất bại (HTTP 502 Bad Gateway - Trụ từ chối ReserveNow):**
```json
{
  "status": 502,
  "detail": "Trụ sạc từ chối yêu cầu ReserveNow từ máy chủ CSMS (Rejected). Vui lòng thử lại.",
  "code": "reserve_now_rejected"
}
```

#### 2.2. API Lấy danh sách đặt chỗ của tài xế
* **Endpoint:** `GET /api/reservations`
* **Quyền hạn:** `driver`, `admin`, `operator`
* **Query Params:** `status=Active`, `page=1`, `page_size=20`

#### 2.3. API Hủy đặt chỗ (tiền đề SCRUM-79)
* **Endpoint:** `POST /api/reservations/{id}/cancel`
* **Quyền hạn:** `driver` (chủ sở hữu đặt chỗ)

---

### 3. Các tệp triển khai và thay đổi

| Thành phần | Đường dẫn file | Mô tả chi tiết |
|---|---|---|
| **Route giao diện** | `backend/app/routers/pages.py` | Đăng ký route `/reservations` phục vụ trang đặt chỗ cho tài xế và quản trị viên. |
| **Menu điều hướng** | `frontend/templates/base.html` | Bổ sung liên kết menu "Đặt chỗ của tôi" tại sidebar cho vai trò tài xế. |
| **Template Đặt chỗ** | `frontend/templates/reservations/list.html` | Xây dựng giao diện danh sách đặt chỗ, banner Active Hero card với countdown timer, modal tạo đặt chỗ mới và modal chi tiết. |
| **Styles (CSS)** | `frontend/static/css/pages/reservations.css` | Thiết kế giao diện hiện đại theo Design System, gradient banner, countdown clock, chip thời gian, badge trạng thái, responsive chuẩn 360px. |
| **Logic (JavaScript)** | `frontend/static/js/pages/reservations.js` | Logic quản lý đặt chỗ, đồng hồ đếm ngược theo giây, cơ chế fallback mock lưu trữ `localStorage` unblock Frontend, bộ lọc & tìm kiếm. |
| **API Client** | `frontend/static/js/api_client.js` | Bổ sung các phương thức: `listReservations`, `createReservation`, `cancelReservation`, `getReservation`. |
| **Lưới giám sát** | `frontend/static/js/pages/monitoring_grid.js` | Tích hợp nút "Đặt trước trụ này" dẫn hướng kèm tham số sang trang đặt chỗ. |
| **Danh sách trạm** | `frontend/templates/stations/list.html` | Bổ sung nút "Đặt trước trụ sạc" cho giao diện tài xế. |
| **Báo cáo kết quả** | `ketqua/SCRUM-76_ket_qua.md` | Tài liệu nghiệm thu và hợp đồng API SCRUM-76. |
| **Nhật ký dự án** | `ketqua/nhat_ky.md` | Ghi nhận tiến độ hoàn thành SCRUM-76 vào nhật ký sprint. |

---

### 4. Ma trận kiểm thử nghiệm thu (Acceptance Test Cases)

| Mã Test | Kịch bản kiểm thử | Kết quả kỳ vọng | Trạng thái |
|:---:|---|---|:---:|
| **TC-76-01** | Truy cập route `/reservations` bằng tài khoản `driver` | Hiển thị đầy đủ trang Đặt chỗ với banner, thẻ thống kê, danh sách lịch sử | **PASS** |
| **TC-76-02** | Bấm nút "Đặt chỗ mới" mở modal tạo đặt chỗ | Modal hiển thị form chọn trạm sạc, các mốc thời gian 15p - 120p, chính sách giữ chỗ | **PASS** |
| **TC-76-03** | Chọn trạm sạc trong dropdown | Danh sách đầu nối tự động lọc và chỉ nạp các đầu nối có trạng thái `Available` (rảnh) | **PASS** |
| **TC-76-04** | Chọn mốc thời gian dự kiến (30 phút, 60 phút) | Mốc thời gian được highlight, hiển thị chính xác giờ hết hạn `display-expiry-target` | **PASS** |
| **TC-76-05** | Xác nhận đặt chỗ thành công (`Accepted`) | Sinh mã `#RES-...`, trụ chuyển trạng thái `Reserved`, kích hoạt Hero Card với đồng hồ đếm ngược | **PASS** |
| **TC-76-06** | Đồng hồ đếm ngược chạy từng giây | Đếm ngược `MM:SS` chính xác; khi về `00:00` chuyển trạng thái sang `Expired` và báo toast | **PASS** |
| **TC-76-07** | Mô phỏng lỗi trụ bận (`Occupied` - 409) | Hiển thị cảnh báo lỗi rõ ràng: trụ/đầu nối đang bận, yêu cầu chọn trụ khác | **PASS** |
| **TC-76-08** | Lọc và tìm kiếm theo mã đặt chỗ / trạm / trạng thái | Bảng danh sách lọc tức thì theo từ khóa nhập vào, không cần reload trang | **PASS** |
| **TC-76-09** | Nhấp nút "Đặt trước trụ này" từ màn hình `/monitoring` | Tự động chuyển sang `/reservations`, mở modal và điền sẵn mã trụ tương ứng | **PASS** |
| **TC-76-10** | Kiểm tra hiển thị responsive trên màn hình mobile 360px | Bố cục co giãn mượt mà, không tràn màn hình, không cuộn ngang | **PASS** |
