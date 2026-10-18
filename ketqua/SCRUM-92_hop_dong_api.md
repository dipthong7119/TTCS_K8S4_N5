# HỢP ĐỒNG API: TÀI XẾ YÊU CẦU XOÁ DỮ LIỆU CÁ NHÂN VÀ LỊCH SỬ DI CHUYỂN

* **Mã công việc**: **SCRUM-92** (Story gốc: **S-57**, Sprint 8, 3 SP)
* **Backend phụ trách**: **Hoàng Văn Đức**
* **Frontend tích hợp**: **Phạm Văn Tuấn** (Giao diện gửi yêu cầu tài xế và quản trị duyệt yêu cầu)
* **Reviewer / QA chéo**: **Ngô Quang Tùng**
* **Trạng thái**: ✅ **Đã hoàn thành và kiểm thử 12/12 unit tests PASSED trên nhánh `feature/SCRUM-92-xoa-du-lieu-ca-nhan`**

---

## 1. TỔNG QUAN VÀ MỤC ĐÍCH NGHIỆP VỤ

API này thực hiện quyền của chủ thể dữ liệu (Data Subject Rights) theo **Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân** và **Quy tắc Agent (Quy tắc 47)**:

1. **Yêu cầu xóa / lãng quên dữ liệu**: Tài xế có quyền gửi yêu cầu xóa dữ liệu cá nhân và lịch sử định vị/di chuyển khỏi hệ thống CSMS.
2. **Kiểm tra điều kiện tiên quyết**:
   - Không được có phiên sạc đang hoạt động (`status == 'active'`).
   - Không được có đặt chỗ đang chờ hoặc đang hoạt động (`status IN ('pending', 'accepted')`).
   - Ví không còn số dư dương (`balance_vnd == 0`). Nếu còn số dư, hệ thống từ chối và hướng dẫn tài xế hoàn tiền/rút tiền trước khi xóa.
   - Chống trùng lặp (Idempotency): Tài xế không thể tạo yêu cầu mới nếu đã có một yêu cầu ở trạng thái `pending`.
3. **Ẩn danh hóa toàn diện không thể đảo ngược (Irreversible Anonymization)**:
   - **Phiên sạc (`charging_sessions`)**: Gán `user_id = NULL`, `driver_name = 'ANONYMIZED'`, `id_tag = NULL`, `id_tag_id = NULL`. Xóa sạch dấu vết tài xế đã sạc ở trạm nào, trụ nào, lúc nào.
   - **Bảo toàn dữ liệu tài chính & đối soát**: Sản lượng điện (`energy_kwh`), thời gian sạc, số đo công tơ (`meter_start_wh`, `meter_stop_wh`), doanh thu trạm và hóa đơn (`charging_invoices`) vẫn **giữ nguyên 100%** để phục vụ đối soát, chia doanh thu và tuân thủ Luật Kế toán.
   - **Thẻ sạc RFID (`id_tags`)**: Khóa thẻ (`is_blocked = True`), đổi mã thẻ thành `ANON_{id}_{hash}` để không tái sử dụng.
   - **Đặt chỗ (`reservations`)**: Ẩn danh hóa `id_tag = 'ANONYMOUS'`, xóa liên kết thẻ.
   - **Tài khoản người dùng (`users`)**: Vô hiệu hóa (`is_active = False`), đổi tên thành `'Người dùng ẩn danh'`, đổi email thành `anonymized_{id}_{hash}@privacy.local`, xóa mật khẩu.
   - **Sổ cái ví (`wallet_ledger`)**: Giữ nguyên toàn bộ các bút toán bất biến (append-only immutability).
4. **Nhật ký kiểm toán (`audit_logs`)**: Ghi nhận minh bạch mọi bước: `privacy.request_created`, `privacy.request_approved`, `privacy.request_rejected`.
5. **Phân quyền bảo mật (Deny-by-default)**:
   - Endpoint tài xế chỉ cho phép vai trò `driver` truy cập.
   - Endpoint quản trị yêu cầu quyền `admin` (phê duyệt/từ chối) hoặc `operator` (xem danh sách).

---

## 2. DANH SÁCH ENDPOINTS CHI TIẾT

### 2.1. Tài xế gửi yêu cầu xóa dữ liệu cá nhân

* **URL**: `POST /api/privacy/erasure-requests`
* **Quyền hạn**: `driver`.

#### Body Request:
```json
{
  "reason": "Tôi không còn sử dụng dịch vụ và yêu cầu xóa thông tin cá nhân theo Nghị định 13/2023/NĐ-CP"
}
```

| Trường | Kiểu | Ràng buộc | Mô tả |
|--------|------|-----------|-------|
| reason | str hoặc null | Tối đa 500 ký tự | Lý do yêu cầu xóa dữ liệu cá nhân. |

#### Phản hồi thành công (HTTP 201 Created):
```json
{
  "id": 1,
  "user_id": 10,
  "driver_name": "Nguyễn Văn A",
  "driver_email": "driver@csms.local",
  "status": "pending",
  "request_reason": "Tôi không còn sử dụng dịch vụ và yêu cầu xóa thông tin cá nhân theo Nghị định 13/2023/NĐ-CP",
  "rejection_reason": null,
  "requested_at": "2026-10-18T08:00:00Z",
  "processed_at": null,
  "processed_by": null,
  "processor_name": null,
  "created_at": "2026-10-18T08:00:00Z",
  "updated_at": "2026-10-18T08:00:00Z"
}
```

* **Mã lỗi thường gặp**:
  - `400 Bad Request`: Đang có phiên sạc hoạt động; hoặc có đặt chỗ chưa hủy; hoặc ví còn số dư > 0 đ.
  - `409 Conflict`: Đã có yêu cầu đang ở trạng thái `pending`.
  - `401 Unauthorized` / `403 Forbidden`: Chưa đăng nhập hoặc không phải tài xế.

---

### 2.2. Tài xế xem danh sách yêu cầu của bản thân

* **URL**: `GET /api/privacy/erasure-requests/my`
* **Quyền hạn**: `driver`.

#### Phản hồi thành công (HTTP 200 OK):
```json
[
  {
    "id": 1,
    "user_id": 10,
    "driver_name": "Nguyễn Văn A",
    "driver_email": "driver@csms.local",
    "status": "pending",
    "request_reason": "Yêu cầu xóa dữ liệu",
    "rejection_reason": null,
    "requested_at": "2026-10-18T08:00:00Z",
    "processed_at": null,
    "processed_by": null,
    "processor_name": null,
    "created_at": "2026-10-18T08:00:00Z",
    "updated_at": "2026-10-18T08:00:00Z"
  }
]
```

---

### 2.3. Quản trị viên/Vận hành xem danh sách các yêu cầu xóa dữ liệu

* **URL**: `GET /api/privacy/admin/erasure-requests`
* **Quyền hạn**: `admin`, `operator`.
* **Query Parameters**:
  - `status`: `pending` | `approved` | `rejected` (tùy chọn)
  - `driver_id`: `int` (tùy chọn)
  - `skip`: `int`, mặc định `0`
  - `limit`: `int`, mặc định `50`, tối đa `100`

#### Phản hồi thành công (HTTP 200 OK):
```json
{
  "items": [
    {
      "id": 1,
      "user_id": 10,
      "driver_name": "Nguyễn Văn A",
      "driver_email": "driver@csms.local",
      "status": "pending",
      "request_reason": "Yêu cầu xóa dữ liệu",
      "rejection_reason": null,
      "requested_at": "2026-10-18T08:00:00Z",
      "processed_at": null,
      "processed_by": null,
      "processor_name": null,
      "created_at": "2026-10-18T08:00:00Z",
      "updated_at": "2026-10-18T08:00:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 50
}
```

---

### 2.4. Quản trị viên phê duyệt và thực hiện ẩn danh hóa

* **URL**: `POST /api/privacy/admin/erasure-requests/{request_id}/approve`
* **Quyền hạn**: `admin`.

#### Phản hồi thành công (HTTP 200 OK):
```json
{
  "id": 1,
  "user_id": 10,
  "driver_name": "Người dùng ẩn danh",
  "driver_email": "anonymized_10_a1b2c3@privacy.local",
  "status": "approved",
  "request_reason": "Yêu cầu xóa dữ liệu",
  "rejection_reason": null,
  "requested_at": "2026-10-18T08:00:00Z",
  "processed_at": "2026-10-18T08:30:00Z",
  "processed_by": 2,
  "processor_name": "Quản Trị Viên Hệ Thống",
  "created_at": "2026-10-18T08:00:00Z",
  "updated_at": "2026-10-18T08:30:00Z"
}
```

* **Mã lỗi thường gặp**:
  - `400 Bad Request`: Yêu cầu không ở trạng thái `pending`; hoặc tài xế phát sinh phiên sạc mới; hoặc ví tài xế có số dư.
  - `403 Forbidden`: Người dùng không có quyền `admin`.
  - `404 Not Found`: Không tìm thấy ID yêu cầu hoặc người dùng.

---

### 2.5. Quản trị viên từ chối yêu cầu xóa dữ liệu

* **URL**: `POST /api/privacy/admin/erasure-requests/{request_id}/reject`
* **Quyền hạn**: `admin`.

#### Body Request:
```json
{
  "rejection_reason": "Tài khoản đang có tranh chấp khiếu nại tài chính chưa xử lý xong."
}
```

| Trường | Kiểu | Ràng buộc | Mô tả |
|--------|------|-----------|-------|
| rejection_reason | str | 3-500 ký tự, bắt buộc | Lý do từ chối yêu cầu. |

#### Phản hồi thành công (HTTP 200 OK):
```json
{
  "id": 1,
  "user_id": 10,
  "driver_name": "Nguyễn Văn A",
  "driver_email": "driver@csms.local",
  "status": "rejected",
  "request_reason": "Yêu cầu xóa dữ liệu",
  "rejection_reason": "Tài khoản đang có tranh chấp khiếu nại tài chính chưa xử lý xong.",
  "requested_at": "2026-10-18T08:00:00Z",
  "processed_at": "2026-10-18T08:30:00Z",
  "processed_by": 2,
  "processor_name": "Quản Trị Viên Hệ Thống",
  "created_at": "2026-10-18T08:00:00Z",
  "updated_at": "2026-10-18T08:30:00Z"
}
```

---

## 3. CHECKLIST KIỂM THỬ VÀ NGHIỆM THU (QA)

| STT | Kịch bản kiểm thử | Kết quả mong đợi | Trạng thái |
|:---:|-------------------|-------------------|:----------:|
| 1 | Driver số dư = 0, không có phiên/đặt chỗ gửi yêu cầu | Tạo thành công (201 Created), status `pending`, ghi audit log | ✅ PASS |
| 2 | Driver đang sạc gửi yêu cầu | Trả về 400 Bad Request kèm lý do | ✅ PASS |
| 3 | Driver có đặt chỗ chưa hủy gửi yêu cầu | Trả về 400 Bad Request kèm lý do | ✅ PASS |
| 4 | Driver ví còn số dư > 0 đ gửi yêu cầu | Trả về 400 Bad Request yêu cầu hoàn tiền trước | ✅ PASS |
| 5 | Driver gửi trùng yêu cầu khi đã có pending | Trả về 409 Conflict | ✅ PASS |
| 6 | Driver xem danh sách yêu cầu của bản thân | Trả về 200 OK đúng danh sách của mình | ✅ PASS |
| 7 | Admin và Operator xem danh sách toàn bộ yêu cầu | Trả về 200 OK, lọc đúng theo status và driver_id | ✅ PASS |
| 8 | Admin duyệt yêu cầu xóa dữ liệu | Ẩn danh hóa ChargingSession, IdTag, Reservation, User; bảo toàn số liệu kế toán; ghi audit log | ✅ PASS |
| 9 | Admin từ chối yêu cầu kèm lý do | Cập nhật status `rejected`, lưu rejection_reason, ghi audit log | ✅ PASS |
| 10 | Operator cố tình duyệt hoặc từ chối yêu cầu | Trả về 403 Forbidden | ✅ PASS |
| 11 | Driver cố tình gọi endpoint duyệt của Admin | Trả về 403 Forbidden | ✅ PASS |
| 12 | Duyệt hoặc từ chối yêu cầu đã được xử lý trước đó | Trả về 400 Bad Request | ✅ PASS |
