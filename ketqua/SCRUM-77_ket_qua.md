# Kết quả thực hiện SCRUM-77 — Xử lý tranh chấp đặt chỗ đồng thời & Gợi ý trụ thay thế

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)  
**Vai trò:** Frontend Developer (Sprint 6-7-8)  
**Epic:** Đặt chỗ trụ sạc (E-07)  
**Story:** SCRUM-77 (S-49: Hai tài xế đặt cùng trụ cùng lúc thì chỉ một người thành công — 3 SP)  
**Người phối hợp Backend:** Ngô Quang Tùng  
**Reviewer:** Trịnh Thanh Tùng (Scrum Master) / Vy Hoàng Tú (FE)  
**Trạng thái:** Hoàn tất 100% triển khai Frontend, Xử lý lỗi tranh chấp HTTP 409, Khối gợi ý trụ thông minh & Bằng chứng kiểm thử  

---

### 1. Mục tiêu và Tiêu chí nghiệm thu (Acceptance Criteria)

- **Mục tiêu:** Đảm bảo khi có tình huống tranh chấp (Race Condition) do hai hoặc nhiều tài xế cùng gửi yêu cầu đặt chỗ vào một đầu nối trong cùng khoảng thời gian, giao diện phía tài xế đến sau xử lý mượt mà, thông báo minh bạch lý do bị từ chối và lập tức **gợi ý các vị trí sạc còn trống khác** để tài xế có thể chọn thay thế chỉ với 1 click.
- **Tiêu chí nghiệm thu (theo đặc tả S-49 / SCRUM-77):**
  1. **Bắt và xử lý chính xác lỗi tranh chấp (HTTP 409 Conflict):**
     - Khi Backend từ chối do xung đột (`reservation_conflict` / `connector_occupied`), Frontend không hiển thị lỗi chung chung mà hiển thị hộp cảnh báo chuyên biệt `.conflict-alert` với hiệu ứng rung nhẹ (Shake animation).
     - Thông báo rõ ràng: *"Trùng lịch đặt chỗ! Vị trí vừa có người đặt trước bạn vài phần trăm giây."*
  2. **Thuật toán quét & Gợi ý vị trí sạc thay thế thông minh (Alternative Suggestions):**
     - Hàm `findAlternativeConnectors()` tự động lọc các đầu nối khác trong cùng trạm sạc đang ở trạng thái `Available` (hoặc `rảnh`).
     - Nếu cùng trạm đã hết chỗ, tự động mở rộng quét sang các trạm lân cận trong hệ thống để tài xế luôn có giải pháp thay thế.
     - Hiển thị danh sách các card gợi ý với đầy đủ thông tin: Mã trụ, Số cổng sạc, Loại súng sạc (CCS2, Type 2, công suất kW) và Badge trạng thái "Rảnh".
  3. **Chuyển đổi một chạm (One-click Switch):**
     - Mỗi gợi ý có nút *"Đặt vị trí này"*. Khi bấm vào, hệ thống tự động cập nhật lại dropdown chọn trụ/đầu nối tương ứng, xóa cảnh báo lỗi và hướng dẫn tài xế bấm nút "Xác nhận đặt chỗ" để hoàn tất ngay mà không phải thao tác lại form từ đầu.
  4. **Chống Double-Submit & Idempotency Key:**
     - Ngăn chặn triệt để hành vi tài xế nhấp đúp liên tục: nút bấm bị vô hiệu hóa (`disabled`) ngay khi click kèm spinner loading.
     - Tự động sinh `idempotency_key` dạng UUID v4 đính kèm payload gửi lên máy chủ để Backend áp dụng cơ chế chống xử lý lặp tại tầng cơ sở dữ liệu.
  5. **Chế độ kiểm thử / Giả lập tranh chấp (Conflict Simulation Mode):**
     - Tích hợp thanh toggle nhỏ *"🧪 Thử nghiệm ca tranh chấp (Giả lập 2 tài xế đặt cùng lúc)"* ngay trong form đặt chỗ.
     - Cho phép QA Tester (Đức, Tùng) và nhóm phát triển kiểm thử ngay lập tức luồng xử lý lỗi 409 và giao diện gợi ý thay thế mà không cần phải dùng 2 máy bắn đồng thời.

---

### 2. Hợp đồng API tranh chấp bàn giao Backend (Ngô Quang Tùng)

* **Endpoint:** `POST /api/reservations`
* **Tham số mới trong Request Body:**
```json
{
  "charge_point_code": "CP_VINCOM_01",
  "connector_id": 1,
  "arrival_minutes": 30,
  "expiry_at": "2026-10-14T12:30:00Z",
  "idempotency_key": "3f9e8a12-87a1-432d-94d7-0123456789ab"
}
```
* **Response khi xảy ra tranh chấp đặt chỗ (HTTP 409 Conflict):**
```json
{
  "status": 409,
  "code": "reservation_conflict",
  "detail": "Vị trí này vừa được một tài xế khác đặt trước bạn. Vui lòng chọn đầu nối khác.",
  "conflicting_charge_point": "CP_VINCOM_01",
  "conflicting_connector_id": 1
}
```

---

### 3. Các tệp triển khai và thay đổi

| Thành phần | Đường dẫn file | Mô tả chi tiết |
|---|---|---|
| **Stylesheet (CSS)** | `frontend/static/css/pages/reservations.css` | Bổ sung class `.conflict-alert`, animation `@keyframes resShake`, `.suggestion-section`, `.suggestion-item`, `.btn-select-suggested` và `.simulation-bar`. |
| **Logic (JavaScript)** | `frontend/static/js/pages/reservations.js` | Viết hàm `findAlternativeConnectors()`, hàm `renderConflictAlert()`, tích hợp sinh `idempotency_key` UUID v4, xử lý chuyển đổi gợi ý nhanh và cờ mô phỏng tranh chấp. |
| **Giao diện Modal** | `frontend/templates/reservations/list.html` | Bổ sung thanh toggle thử nghiệm tranh chấp `#conflict-simulation-wrap`, tối ưu vùng phản hồi lỗi `#reserve-feedback`. |
| **Báo cáo kết quả** | `ketqua/SCRUM-77_ket_qua.md` | Tài liệu nghiệm thu các tiêu chí SCRUM-77 / S-49 và hợp đồng API tranh chấp. |
| **Nhật ký dự án** | `ketqua/nhat_ky.md` | Cập nhật tiến độ hoàn thành SCRUM-77 vào nhật ký sprint. |

---

### 4. Ma trận kiểm thử nghiệm thu (Acceptance Test Cases)

| Mã Test | Kịch bản kiểm thử | Kết quả kỳ vọng | Trạng thái |
|:---:|---|---|:---:|
| **TC-77-01** | Bật toggle *"Thử nghiệm ca tranh chấp"* và bấm "Xác nhận đặt chỗ" | Giao diện chặn thành công, hiển thị khối thông báo tranh chấp màu cam kèm rung nhẹ | **PASS** |
| **TC-77-02** | Khối thông báo tranh chấp xuất hiện | Hiển thị chính xác icon cảnh báo, thông điệp vị trí vừa có người đặt trước và danh sách gợi ý | **PASS** |
| **TC-77-03** | Khối gợi ý trụ thay thế hiển thị các đầu nối rảnh | Hiển thị đúng các đầu nối `Available` trong cùng trạm (hoặc trạm lân cận), không chứa đầu nối đang xung đột | **PASS** |
| **TC-77-04** | Bấm nút *"Đặt vị trí này"* trên một card gợi ý | Form tự động cập nhật sang đầu nối gợi ý, toggle mô phỏng tự tắt và thông báo hướng dẫn hoàn tất | **PASS** |
| **TC-77-05** | Bấm lại "Xác nhận đặt chỗ" sau khi đã chuyển sang đầu nối gợi ý | Đặt chỗ thành công với đầu nối mới, chuyển sang màn hình Hero Card đếm ngược | **PASS** |
| **TC-77-06** | Kiểm tra chống Double-Submit (nhấp liên tục nút xác nhận) | Nút xác nhận bị khóa `disabled` ngay lập tức với spinner loading, không thể gửi 2 request trùng | **PASS** |
| **TC-77-07** | Kiểm tra tham số `idempotency_key` | Request payload luôn mang mã UUID v4 duy nhất cho mỗi lượt gửi | **PASS** |
| **TC-77-08** | Kiểm tra responsive trên màn hình điện thoại 360px | Khối cảnh báo và danh sách gợi ý co giãn mượt mà, nút chọn trụ vừa vặn không bị tràn khung | **PASS** |
