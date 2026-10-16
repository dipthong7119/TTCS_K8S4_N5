# HỢP ĐỒNG API: NHẬT KÝ THAO TÁC TRÊN GIAO DỊCH VÍ

* **Mã công việc**: **SCRUM-91** (Story gốc: **S-56**, Sprint 8, 3 SP)
* **Backend phụ trách**: **Hoàng Văn Đức**
* **Frontend tích hợp**: **Phạm Văn Tuấn** (Màn hình nhật ký tra cứu giao dịch ví `admin_drivers.html`)
* **Reviewer / QA chéo**: **Ngô Quang Tùng**
* **Trạng thái**: ✅ **Đã hoàn thành và kiểm thử 11/11 test PASSED trên nhánh `feature/SCRUM-91-nhat-ky-giao-dich-vi`**

---

## 1. TỔNG QUAN VÀ MỤC ĐÍCH NGHIỆP VỤ

API này phục vụ cho việc **kiểm toán toàn bộ thao tác trên ví tài xế** — truy được ai đã làm gì vào ví nào, lúc nào:

1. **Nhật ký nạp tay (`wallet.manual_topup`)**: Mỗi lần Admin nạp tiền thủ công cho tài xế, hệ thống ghi rõ người thực hiện, tài xế được nạp, số tiền, mã phiếu thu và lý do.
2. **Nhật ký điều chỉnh số dư (`wallet.adjust`)**: Admin có thể cộng hoặc trừ số dư tùy chỉnh (bồi hoàn, xử lý sự cố), bắt buộc phải có lý do; mỗi thao tác tạo một bút toán sổ cái và một dòng nhật ký kiểm toán.
3. **Nhật ký khóa / mở khóa ví (`wallet.lock` / `wallet.unlock`)**: Admin khóa hoặc mở khóa tài khoản tài xế kèm lý do bắt buộc; ghi nhật ký để tra cứu.
4. **Tra cứu nhật ký**: API lọc theo `driver_id`, tên/email tài xế (`driver`), và loại hành động (`action`).
5. **Tính bất biến (Immutability)**: Bảng `audit_logs` là **append-only** — mọi thao tác sửa/xóa qua API đều bị từ chối bằng HTTP **405 Method Not Allowed**.
6. **Phân quyền bảo mật**: Chỉ vai trò `admin` và `operator` mới có quyền tra cứu nhật ký (Deny-by-default).

---

## 2. DANH SÁCH ENDPOINTS CHI TIẾT

### 2.1. Điều chỉnh số dư ví tài xế

* **URL**: `POST /api/wallet/admin/wallets/{driver_user_id}/adjust`
* **Quyền hạn**: `admin`.

#### Body Request:
```json
{
  "amount_vnd": 50000,
  "reason": "Bồi hoàn phiên sạc bị gián đoạn do lỗi hệ thống",
  "reference_code": "REF-20261013-001"
}
```

| Trường | Kiểu | Ràng buộc | Mô tả |
|--------|------|-----------|-------|
| amount_vnd | int | Khác 0 | Số tiền điều chỉnh (dương=cộng, âm=trừ). Đơn vị: đồng VND. |
| reason | str | 3-200 ký tự, bắt buộc | Lý do điều chỉnh. |
| reference_code | str hoặc null | Tối đa 80 ký tự | Mã tham chiếu tùy chọn. |

#### Phản hồi thành công (HTTP 201 Created):
```json
{
  "entry_id": 42,
  "driver_id": 10,
  "amount_vnd": 50000,
  "entry_type": "adjustment",
  "balance_after_vnd": 150000,
  "created_at": "2026-10-13T09:30:00Z"
}
```

Lỗi: 400 (amount=0 hoặc reason ngắn), 403 (không phải admin), 404 (tài xế không tồn tại).

---

### 2.2. Khóa ví tài xế

* **URL**: `POST /api/wallet/admin/wallets/{driver_user_id}/lock`
* **Quyền hạn**: `admin`.
* **Body**: `{"reason": "Nghi vấn giao dịch bất thường"}`
* **Phản hồi 200**: `{"driver_id": 10, "status": "locked", "reason": "..."}`

---

### 2.3. Mở khóa ví tài xế

* **URL**: `POST /api/wallet/admin/wallets/{driver_user_id}/unlock`
* **Quyền hạn**: `admin`.
* **Body**: `{"reason": "Đã xác minh thông tin, tài xế an toàn"}`
* **Phản hồi 200**: `{"driver_id": 10, "status": "active", "reason": "..."}`

---

### 2.4. Tra cứu nhật ký kiểm toán (mở rộng SCRUM-91)

* **URL**: `GET /api/audit`
* **Quyền hạn**: `admin`, `operator`.

| Tham số | Kiểu | Mô tả |
|---------|------|-------|
| driver_id | int | Lọc theo ID tài xế (target_user_id). |
| driver | str | Lọc theo tên hoặc email tài xế (tìm kiếm mờ). |
| action | str | Lọc theo loại hành động (wallet.adjust, wallet.lock...). |
| actor | str | Lọc theo tên hoặc email người thực hiện. |
| date_from | date | Lọc từ ngày (YYYY-MM-DD). |
| date_to | date | Lọc đến ngày (YYYY-MM-DD). |
| page | int | Số trang (mặc định: 1). |
| page_size | int | Dòng/trang (mặc định: 50, tối đa: 50). |

#### Phản hồi thành công (HTTP 200 OK):
```json
{
  "items": [
    {
      "id": 101,
      "actor_id": 1,
      "actor_email": "admin@charge.vn",
      "actor_name": "Nguyễn Quản Trị",
      "target_user_id": 10,
      "action": "wallet.adjust",
      "object_type": "wallet",
      "object_id": "42",
      "charge_point_code": null,
      "details": {
        "driver_id": 10,
        "driver_email": "driver1@gmail.com",
        "driver_name": "Tài Xế Một",
        "amount_vnd": 50000,
        "reason": "Bồi hoàn phiên sạc bị gián đoạn",
        "reference_code": "REF-20261013-001"
      },
      "created_at": "2026-10-13T09:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

---

### 2.5. Bảo vệ tính bất biến (Append-Only)

Mọi PUT/PATCH/DELETE trên `/api/audit/{id}` => `405 Method Not Allowed`
Response: `{"detail": "Nhật ký kiểm toán chỉ được đọc"}`

---

## 3. BẢNG HÀNH ĐỘNG KIỂM TOÁN VÀ NỘI DUNG details

| action | Khi nào | Nội dung details |
|--------|---------|-----------------|
| wallet.manual_topup | Admin nạp tay | driver_email, driver_name, amount_vnd, receipt_code, reason |
| wallet.adjust | Admin điều chỉnh số dư | driver_id, driver_email, driver_name, amount_vnd, reason, reference_code |
| wallet.lock | Admin khóa ví | driver_id, driver_email, driver_name, reason, is_locked: true |
| wallet.unlock | Admin mở khóa ví | driver_id, driver_email, driver_name, reason, is_locked: false |

---

## 4. GỢI Ý TÍCH HỢP CHO FRONTEND (PHẠM VĂN TUẤN)

### 4.1. Trang Quản lý tài xế (admin_drivers.html)

1. **Tab "Nhật ký ví"** — Gọi `GET /api/audit?driver_id={id}` khi mở tab.
   * Hiển thị bảng: Thời gian | Người thực hiện | Hành động | Số tiền | Lý do.
   * Dropdown lọc action: Tất cả / Nạp tiền / Điều chỉnh / Khóa ví / Mở khóa.

2. **Nút "Điều chỉnh số dư"** — Modal: Số tiền (+/-), Lý do (bắt buộc ≥3 ký tự), Mã tham chiếu (tùy chọn).
   * Gọi `POST /api/wallet/admin/wallets/{id}/adjust`.
   * Khi thành công: Toast, cập nhật số dư, reload nhật ký.

3. **Nút "Khóa ví" / "Mở khóa ví"** — Modal xác nhận kèm ô lý do bắt buộc.
   * Gọi `POST /api/wallet/admin/wallets/{id}/lock` hoặc `.../unlock`.

### 4.2. Lưu ý kỹ thuật

* Mọi lời gọi API phải đi qua `static/js/api_client.js`.
* Số tiền là **số nguyên đồng VND** — hiển thị `50.000 đồng`.
* Dịch action sang tiếng Việt: wallet.adjust => Điều chỉnh số dư, wallet.lock => Khóa ví.
