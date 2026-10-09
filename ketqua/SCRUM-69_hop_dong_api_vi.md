# HỢP ĐỒNG API: NẠP VÍ QUA CỔNG THANH TOÁN SANDBOX & QUẢN LÝ SỐ DƯ (SCRUM-69)

**Người phụ trách Backend:** Hoàng Văn Đức  
**Chuyển giao cho:** Phạm Văn Tuấn (Frontend - SCRUM-195, SCRUM-200), Trịnh Thanh Tùng (SCRUM-73), Tạ Như Vinh (SCRUM-72)  
**Ngày ban hành:** 09/10/2026  
**Trạng thái:** Sẵn sàng kết nối Frontend (Mock hoặc Real API)  

---

## 1. Tổng quan các Endpoint

| Method | Đường dẫn API | Quyền (Roles) | Mô tả | Mã Jira liên quan |
|---|---|---|---|---|
| `POST` | `/api/wallet/topups/sandbox` | `driver` | Khởi tạo đơn nạp tiền sandbox | SCRUM-196, 197 |
| `POST` | `/api/wallet/topups/sandbox/webhook` | Công khai / Gateway | Webhook nhận kết quả từ cổng sandbox (idempotent) | SCRUM-198, 73 |
| `POST` | `/api/wallet/topups/sandbox/simulate-pay` | `driver` | Giả lập thanh toán nhanh trực tiếp từ giao diện | SCRUM-196, 198 |
| `GET` | `/api/wallet/topups` | `driver` | Lấy lịch sử các yêu cầu nạp tiền của tài xế | SCRUM-197, 200 |
| `GET` | `/api/wallet` | `driver` | Lấy số dư hiện tại và tổng chi tiêu | SCRUM-200 |
| `GET` | `/api/wallet/check-balance` | `driver`, `operator`, `admin` | Kiểm tra số dư tối thiểu trước khi bắt đầu sạc | SCRUM-199, 72 |

---

## 2. Chi tiết hợp đồng API

### 2.1. Khởi tạo đơn nạp tiền sandbox
* **Endpoint:** `POST /api/wallet/topups/sandbox`
* **Headers:** `Content-Type: application/json`
* **Request Body:**
  ```json
  {
    "amount_vnd": 100000
  }
  ```
  *(Ràng buộc: `amount_vnd` tối thiểu 10.000 VNĐ, tối đa 10.000.000 VNĐ)*
* **Response (HTTP 201 Created):**
  ```json
  {
    "order_code": "TOPUP-20261009163000-A1B2C3",
    "amount_vnd": 100000,
    "status": "pending",
    "provider": "sandbox",
    "payment_url": "/wallet/sandbox-checkout?order_code=TOPUP-20261009163000-A1B2C3",
    "created_at": "2026-10-09T16:30:00.123456Z"
  }
  ```

---

### 2.2. Webhook nhận kết quả từ Cổng Sandbox
* **Endpoint:** `POST /api/wallet/topups/sandbox/webhook`
* **Tính chất:** Hỗ trợ xử lý lặp lại an toàn (Idempotent) — gọi nhiều lần cùng `order_code` không bị cộng tiền trùng.
* **Request Body:**
  ```json
  {
    "order_code": "TOPUP-20261009163000-A1B2C3",
    "status": "success",
    "failure_reason": null,
    "signature": "hmac_sha256_hash_here"
  }
  ```
* **Response (HTTP 200 OK):**
  ```json
  {
    "order_code": "TOPUP-20261009163000-A1B2C3",
    "status": "success",
    "amount_vnd": 100000,
    "user_id": 10,
    "balance_vnd": 250000
  }
  ```

---

### 2.3. Giả lập thanh toán nhanh từ UI (Simulate Pay)
Dành cho Frontend khi tài xế bấm nút "Xác nhận đã thanh toán Sandbox" trên modal:
* **Endpoint:** `POST /api/wallet/topups/sandbox/simulate-pay`
* **Request Body:**
  ```json
  {
    "order_code": "TOPUP-20261009163000-A1B2C3",
    "status": "success"
  }
  ```
* **Response (HTTP 200 OK):**
  ```json
  {
    "order_code": "TOPUP-20261009163000-A1B2C3",
    "status": "success",
    "amount_vnd": 100000,
    "balance_vnd": 250000
  }
  ```

---

### 2.4. Lấy lịch sử nạp tiền của tài xế
* **Endpoint:** `GET /api/wallet/topups?page=1&page_size=20`
* **Response (HTTP 200 OK):**
  ```json
  {
    "items": [
      {
        "id": 1,
        "order_code": "TOPUP-20261009163000-A1B2C3",
        "amount_vnd": 100000,
        "status": "success",
        "provider": "sandbox",
        "payment_url": "/wallet/sandbox-checkout?order_code=TOPUP-20261009163000-A1B2C3",
        "failure_reason": null,
        "created_at": "2026-10-09T16:30:00Z",
        "updated_at": "2026-10-09T16:30:15Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
  ```

---

### 2.5. Kiểm tra số dư ví tối thiểu (Trước khi kích hoạt sạc)
* **Endpoint:** `GET /api/wallet/check-balance?min_amount_vnd=50000`
* **Response (HTTP 200 OK):**
  ```json
  {
    "user_id": 10,
    "balance_vnd": 250000,
    "minimum_required_vnd": 50000,
    "has_minimum_balance": true
  }
  ```
  *(Nếu `has_minimum_balance == false`, Frontend hiển thị thông báo nhắc tài xế nạp ví).*
