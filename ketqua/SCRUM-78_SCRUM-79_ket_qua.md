# Kết quả thực hiện SCRUM-78 & SCRUM-79 — Quá hạn giữ chỗ tính phí & Hủy đặt chỗ chủ động

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)  
**Vai trò:** Frontend Developer (Sprint 6-7-8)  
**Epic:** Đặt chỗ trụ sạc (E-07)  
**Stories hoàn thành:**  
- **SCRUM-78 (S-50):** Giữ chỗ quá giờ không tới thì bị huỷ và tính phí (3 SP)  
- **SCRUM-79 (S-51):** Tài xế huỷ chỗ đã đặt và trụ mở lại cho người khác (3 SP)  
**Người phối hợp Backend:** Ngô Quang Tùng  
**Reviewer:** Trịnh Thanh Tùng (Scrum Master) / Vy Hoàng Tú (FE)  
**Trạng thái:** Hoàn tất 100% triển khai Frontend, Tích hợp đếm ngược quá hạn, Phí phạt không đến, Modal hủy đặt chỗ, Mở lại trụ sạc & Liên kết ví tài xế  

---

### 1. Mục tiêu và Tiêu chí nghiệm thu (Acceptance Criteria)

#### 1.1. SCRUM-78 (S-50) — Quá hạn giữ chỗ & Tính phí phạt không đến (No-show Fee)
* **AC-78-1 (Phát hiện hết hạn thời gian thực):** Khi đồng hồ đếm ngược giữ chỗ còn lại chạm mốc `00:00` hoặc khi hệ thống phát hiện `expiry_at <= Date.now()`, lượt đặt chỗ lập tức tự động chuyển từ `Active` sang trạng thái `Expired` (Quá hạn).
* **AC-78-2 (Banner cảnh báo quá hạn chuyên biệt):** Hiển thị khối thông báo màu cam đỏ nổi bật `#expired-notice-container` thông báo rõ: Lượt đặt chỗ `RES-...` tại trạm sạc đã quá hạn, trụ đã được tự động mở lại cho tài xế khác và phí phạt giữ chỗ không đến `15.000 ₫` đã được ghi nhận.
* **AC-78-3 (Tính phí phạt & Tích hợp Ví):** Ghi nhận khoản phí phạt `no_show_fee_vnd: 15000`. Trên bảng lịch sử hiển thị badge phạt `-15.000 ₫` màu đỏ kèm nút link trực tiếp sang `/wallet` (tích hợp ví tài xế của Tuấn SCRUM-74) để tài xế tra cứu giao dịch trừ tiền.
* **AC-78-4 (Giải phóng đầu nối sạc):** Đầu nối sạc được giải phóng ngay lập tức, chuyển trạng thái từ `Reserved` về `Available` (Rảnh) để người khác có thể đặt hoặc cắm sạc.
* **AC-78-5 (Chip kiểm thử nhanh 6 giây):** Cung cấp chip lựa chọn thời gian thử nghiệm nhanh `⏱ 6s (Test SCRUM-78)` trong modal đặt chỗ giúp QA và SM kiểm thử kịch bản hết hạn tự động ngay trong 6 giây mà không cần chờ 15–30 phút.

#### 1.2. SCRUM-79 (S-51) — Hủy đặt chỗ chủ động & Trụ mở lại cho người khác
* **AC-79-1 (Hủy trước hạn miễn phí 100%):** Nếu tài xế chủ động hủy khi lượt đặt chỗ còn trong thời hạn (`status === 'Active'`), hệ thống không thu bất kỳ khoản phí nào (`no_show_fee_vnd = 0`). Thông báo rõ ràng: *"Hủy trước hạn hoàn toàn MIỄN PHÍ"*.
* **AC-79-2 (Modal xác nhận hủy chuyên nghiệp `#modal-cancel-confirm`):** Hiển thị tóm tắt thông tin mã đặt chỗ, trạm sạc, trụ sạc & đầu nối. Bắt buộc tài xế chọn lý do hủy (Thay đổi kế hoạch, Đã tìm được trạm gần hơn, Pin còn đủ, Bị tắc đường,...).
* **AC-79-3 (Bản tin OCPP CancelReservation):** Gửi yêu cầu hủy tới máy chủ CSMS qua `ApiClient.cancelReservation(id, { reason })` để hạ bản tin OCPP `CancelReservation` xuống trụ sạc vật lý. Nút bấm có trạng thái loading spinner ngăn double-click.
* **AC-79-4 (Mở lại trụ sạc ngay lập tức):** Ngay sau khi hủy, trụ sạc được giải phóng ngay tại máy trạm và cây giám sát, trạng thái chuyển về `Available` / `rảnh`.
* **AC-79-5 (Chặn hủy lượt đã quá hạn):** Nếu lượt đặt chỗ đã ở trạng thái `Expired`, nút hủy bị vô hiệu hóa hoặc chặn thông báo: *"Không thể hủy lượt đặt chỗ đã quá hạn vì đã tính phí giữ chỗ."*
* **AC-79-6 (Điểm truy cập thao tác thuận tiện):** Tài xế có thể hủy từ 3 vị trí: (1) Nút "Hủy đặt chỗ này" trên Hero Card đang giữ chỗ, (2) Nút "Hủy" trên từng dòng bảng lịch sử, (3) Nút "Hủy đặt chỗ này" trong Modal xem chi tiết.

---

### 2. Hợp đồng API bàn giao Backend (Ngô Quang Tùng)

#### 2.1. API Hủy đặt chỗ chủ động (SCRUM-79)
* **Endpoint:** `POST /api/reservations/{id}/cancel`
* **Request Body:**
```json
{
  "reason": "Thay đổi kế hoạch di chuyển",
  "note": "Tài xế chủ động hủy trên web portal"
}
```
* **Response (HTTP 200 OK):**
```json
{
  "status": "success",
  "reservation_id": 101,
  "reservation_code": "RES-20261014-001",
  "new_status": "Cancelled",
  "cancelled_at": "2026-10-15T03:20:00Z",
  "cancellation_reason": "Thay đổi kế hoạch di chuyển",
  "no_show_fee_vnd": 0,
  "ocpp_message_sent": "CancelReservation",
  "ocpp_status": "Accepted",
  "charge_point_code": "CP_VINCOM_01",
  "connector_id": 1,
  "connector_status": "Available"
}
```

#### 2.2. API Quá hạn giữ chỗ & Phí phạt không đến (SCRUM-78)
* **Cơ chế:** Background Worker / Cronjob quét các lượt `Active` có `expiry_at <= NOW()`.
* **Bút toán ví (Wallet Ledger entry):**
```json
{
  "driver_id": 1,
  "transaction_type": "no_show_penalty",
  "amount_vnd": -15000,
  "reference_id": "RES-20261014-001",
  "description": "Phí phạt không đến giữ chỗ trụ CP_VINCOM_01 quá hạn 30 phút",
  "created_at": "2026-10-15T03:30:00Z"
}
```
* **Bản tin OCPP gửi trụ:** OCPP `CancelReservation(reservationId)` để hủy khóa trên trụ sạc và chuyển connector về `Available`.

---

### 3. Các thành phần giao diện & Logic đã hoàn thành

| Thành phần | File mã nguồn | Mô tả chi tiết |
| :--- | :--- | :--- |
| **Modal xác nhận hủy** | `frontend/templates/reservations/list.html` | Modal `#modal-cancel-confirm` gồm tóm tắt mã, trạm, cổng, thông báo miễn phí, dropdown lý do hủy và nút xác nhận |
| **Banner quá hạn** | `frontend/templates/reservations/list.html` | Container `#expired-notice-container` render banner đỏ-cam cảnh báo quá hạn, trừ phí 15k và link ví |
| **Chip test 6s** | `frontend/templates/reservations/list.html` | Nút `⏱ 6s (Test SCRUM-78)` trong form đặt chỗ mới giúp kiểm thử quá hạn tức thì |
| **CSS Style** | `frontend/static/css/pages/reservations.css` | Các lớp `.cancel-summary-box`, `.cancel-policy-notice`, `.expired-alert-banner`, `.no-show-badge`, `.wallet-link-chip` |
| **Logic JS Expiry & Cancel** | `frontend/static/js/pages/reservations.js` | Hàm `releaseConnector()`, `renderExpiredNotice()`, `openCancelModal()`, `handleCancelSubmit()`, kiểm tra quá hạn trong `updateCountdownDisplay()` & `loadReservations()` |
| **ApiClient** | `frontend/static/js/api_client.js` | Mở rộng `cancelReservation(id, body, opts)` hỗ trợ gửi kèm `reason` |

---

### 4. Ma trận kiểm thử (Test Matrix)

| Mã test case | Nội dung kiểm thử | Thao tác thực hiện | Kết quả mong đợi | Trạng thái |
| :--- | :--- | :--- | :--- | :---: |
| **TC-78-01** | Tự động phát hiện hết hạn | Tạo đặt chỗ với chip `⏱ 6s (Test SCRUM-78)`, chờ đồng hồ về 00:00 | Trạng thái đổi sang `Expired`, đếm ngược dừng, còi toast cảnh báo hiện ra | **PASS** |
| **TC-78-02** | Hiển thị Banner cảnh báo quá hạn | Đồng hồ hết hạn hoặc tải trang có lượt đã quá hạn | Banner xuất hiện phía trên cùng, thông báo rõ phí phạt 15.000 ₫ và có nút xem ví | **PASS** |
| **TC-78-03** | Badge phí phạt trên bảng | Xem bảng lịch sử sau khi hết hạn | Dưới giờ hết hạn có badge `-15.000 ₫`, cột thao tác có nút "Ví" | **PASS** |
| **TC-78-04** | Trụ sạc mở lại sau hết hạn | Mở modal đặt chỗ mới sau khi lượt cũ hết hạn | Đầu nối vừa hết hạn xuất hiện lại trong dropdown chọn cổng (Available) | **PASS** |
| **TC-78-05** | Chi tiết lượt đặt chỗ quá hạn | Bấm "Chi tiết" tại dòng quá hạn | Modal chi tiết hiện thông báo đỏ giải thích nguyên nhân và nút mở biến động ví | **PASS** |
| **TC-79-01** | Mở Modal xác nhận hủy | Bấm nút "Hủy" tại card đang giữ chỗ hoặc bảng | Modal `#modal-cancel-confirm` hiện lên với thông tin chính xác trạm và trụ | **PASS** |
| **TC-79-02** | Hủy thành công trước hạn | Chọn lý do "Thay đổi kế hoạch di chuyển" và bấm "Xác nhận hủy" | Nút xoay spinner, thông báo thành công, trạng thái chuyển `Cancelled`, phí 0 ₫ | **PASS** |
| **TC-79-03** | Trụ sạc mở lại cho người khác | Sau khi hủy, kiểm tra danh sách đầu nối rảnh | Đầu nối lập tức trở lại trạng thái `Available` cho phép người khác đặt | **PASS** |
| **TC-79-04** | Chặn hủy lượt đã quá hạn | Thử tìm cách hủy lượt `Expired` | Hệ thống chặn cảnh báo: "Không thể hủy lượt đặt chỗ đã quá hạn..." | **PASS** |
| **TC-79-05** | Hủy từ trong Modal chi tiết | Mở modal chi tiết của lượt Active, bấm nút "Hủy đặt chỗ này" | Đóng modal chi tiết và mở tiếp modal xác nhận hủy trơn tru | **PASS** |
