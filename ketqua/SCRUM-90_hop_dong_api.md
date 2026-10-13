# HỢP ĐỒNG API: CẢNH BÁO TRỤ NGOẠI TUYẾN VÀ LỖI LIÊN TỤC

* **Mã công việc**: **SCRUM-90** (Story gốc: **S-46**, Sprint 6, 3 SP)
* **Backend phụ trách**: **Hoàng Văn Đức**
* **Frontend tích hợp**: **Phạm Văn Tuấn** (Hiển thị cảnh báo đầu màn hình giám sát và nút đóng cảnh báo)
* **Reviewer / QA chéo**: **Ngô Quang Tùng**
* **Trạng thái**: ✅ **Đã hoàn thành và kiểm thử 100% trên nhánh `feature/SCRUM-90-canh-bao-offline-va-loi`**

---

## 1. TỔNG QUAN VÀ MỤC ĐÍCH NGHIỆP VỤ

API này phục vụ cho việc giám sát vận hành trạm sạc:
1. **Cảnh báo ngoại tuyến (`offline`)**: Tự động phát hiện các trụ không gửi tin nhắn/nhịp tim quá 15 phút (`ALERT_OFFLINE_THRESHOLD_MINUTES`).
2. **Cảnh báo lỗi liên tục (`connector_error`)**: Tự động phát hiện các đầu nối báo từ 3 lỗi trở lên (`ALERT_ERROR_COUNT_THRESHOLD`) trong vòng 10 phút gần đây (`ALERT_ERROR_WINDOW_MINUTES`).
3. **Chống trùng lặp (Deduplication)**: Cùng một trụ sạc / đầu nối, nếu đã có cảnh báo đang kích hoạt (`status: 'active'`), hệ thống **tuyệt đối không** sinh cảnh báo mới cho đến khi cảnh báo cũ được đóng (`resolved`).
4. **Phân quyền bảo mật**: Chỉ vai trò `admin` và `operator` mới có quyền truy cập (Deny-by-default).

---

## 2. DANH SÁCH ENDPOINTS CHI TIẾT

### 2.1. Lấy danh sách cảnh báo (Hỗ trợ phân trang và bộ lọc)

* **URL**: `GET /api/alerts`
* **Xác thực**: Session Cookie (`credentials: 'include'`).
* **Quyền hạn**: `operator`, `admin`.
* **Query Parameters**:
  * `status` *(optional, string)*: Lọc theo trạng thái (`active` hoặc `resolved`). Nếu bỏ trống sẽ lấy tất cả.
  * `alert_type` *(optional, string)*: Lọc theo loại (`offline` hoặc `connector_error`).
  * `charge_point_id` *(optional, int)*: Lọc theo ID trụ sạc cụ thể.
  * `skip` *(optional, int, default: 0)*: Số bản ghi bỏ qua (phân trang).
  * `limit` *(optional, int, default: 50, max: 100)*: Số bản ghi tối đa trên một trang.

#### Ví dụ Request:
```http
GET /api/alerts?status=active&limit=10 HTTP/1.1
```

#### Phản hồi thành công (HTTP 200 OK):
```json
{
  "total": 2,
  "active_count": 2,
  "items": [
    {
      "id": 1,
      "charge_point_id": 2,
      "charge_point_code": "CP_02",
      "connector_id": null,
      "alert_type": "offline",
      "severity": "critical",
      "status": "active",
      "message": "Trụ sạc CP_02 ngoại tuyến quá 15 phút. Lần liên lạc cuối: 2026-10-13 14:10:00.",
      "error_count": null,
      "triggered_at": "2026-10-13T14:26:00",
      "resolved_at": null,
      "resolved_by_id": null,
      "created_at": "2026-10-13T14:26:00",
      "updated_at": "2026-10-13T14:26:00"
    },
    {
      "id": 2,
      "charge_point_id": 1,
      "charge_point_code": "CP_01",
      "connector_id": 1,
      "alert_type": "connector_error",
      "severity": "warning",
      "status": "active",
      "message": "Đầu nối 1 của trụ CP_01 ghi nhận 4 lỗi liên tiếp trong 10 phút gần đây.",
      "error_count": 4,
      "triggered_at": "2026-10-13T14:30:00",
      "resolved_at": null,
      "resolved_by_id": null,
      "created_at": "2026-10-13T14:30:00",
      "updated_at": "2026-10-13T14:30:00"
    }
  ]
}
```

---

### 2.2. Lấy số lượng thống kê nhanh (Dashboard Summary Badge)

Phục vụ hiển thị badge số lượng cảnh báo nổi bật ở đầu trang theo dõi vận hành hoặc thanh thông báo (Navbar / Header).

* **URL**: `GET /api/alerts/summary`
* **Xác thực**: Session Cookie (`credentials: 'include'`).
* **Quyền hạn**: `operator`, `admin`.

#### Phản hồi thành công (HTTP 200 OK):
```json
{
  "active_total": 2,
  "active_offline": 1,
  "active_connector_error": 1
}
```

---

### 2.3. Đóng cảnh báo (Resolve Alert)

Vận hành viên hoặc quản trị viên sau khi xử lý xong sự cố ngoài hiện trường hoặc kiểm tra hệ thống thì bấm nút "Đóng cảnh báo" trên giao diện.

* **URL**: `POST /api/alerts/{alert_id}/resolve`
* **Xác thực**: Session Cookie (`credentials: 'include'`).
* **Quyền hạn**: `operator`, `admin`.
* **Path Parameter**:
  * `alert_id` *(int)*: ID của cảnh báo cần đóng (ví dụ: `1`).
* **Body Request** *(JSON, tùy chọn)*:
```json
{
  "note": "Kỹ thuật viên đã kiểm tra và đóng lại aptomat nguồn tại trạm."
}
```

#### Phản hồi thành công (HTTP 200 OK):
```json
{
  "id": 1,
  "charge_point_id": 2,
  "charge_point_code": "CP_02",
  "connector_id": null,
  "alert_type": "offline",
  "severity": "critical",
  "status": "resolved",
  "message": "Trụ sạc CP_02 ngoại tuyến quá 15 phút. Lần liên lạc cuối: 2026-10-13 14:10:00. [Ghi chú giải quyết: Kỹ thuật viên đã kiểm tra và đóng lại aptomat nguồn tại trạm.]",
  "error_count": null,
  "triggered_at": "2026-10-13T14:26:00",
  "resolved_at": "2026-10-13T15:00:00",
  "resolved_by_id": 3,
  "created_at": "2026-10-13T14:26:00",
  "updated_at": "2026-10-13T15:00:00"
}
```

#### Các mã lỗi có thể gặp:
* `401 Unauthorized`: Chưa đăng nhập.
* `403 Forbidden`: Người dùng không có vai trò `admin` hoặc `operator`.
* `404 Not Found`: Không tìm thấy cảnh báo với ID chỉ định (`{"detail": "Không tìm thấy cảnh báo với ID 999"}`).

---

### 2.4. Kích hoạt quét thủ công (On-Demand Scan)

* **URL**: `POST /api/alerts/scan`
* **Xác thực**: Session Cookie (`credentials: 'include'`).
* **Quyền hạn**: `operator`, `admin`.
* **Mô tả**: Quét ngay lập tức toàn bộ hệ thống để tìm trụ offline và lỗi đầu nối, trả về danh sách các cảnh báo mới vừa được sinh ra (nếu có).

---

## 3. GỢI Ý TÍCH HỢP CHO FRONTEND (PHẠM VĂN TUẤN)

1. **Hiển thị đầu trang theo dõi (`monitoring.html`)**:
   * Gọi `GET /api/alerts/summary` khi tải trang:
     * Nếu `active_total > 0`, hiển thị một banner cảnh báo màu đỏ/vàng ở đầu trang:
       * *"Hệ thống phát hiện **X** trụ ngoại tuyến quá lâu và **Y** đầu nối báo lỗi liên tục."*
       * Kèm nút *"Xem chi tiết"* mở drawer/modal danh sách cảnh báo.
2. **Modal / Danh sách cảnh báo**:
   * Gọi `GET /api/alerts?status=active`.
   * Hiển thị bảng gồm: Mã trụ, Loại sự cố (Offline / Lỗi đầu nối), Mức độ (Critical / Warning), Thời gian kích hoạt, Nội dung thông báo.
   * Cột Thao tác: Nút *"Đóng cảnh báo"*.
3. **Hành động Đóng cảnh báo**:
   * Khi bấm nút *"Đóng cảnh báo"*, mở pop-up xác nhận kèm ô nhập ghi chú phương án xử lý (`note`).
   * Gọi `POST /api/alerts/{id}/resolve`.
   * Khi thành công: Hiển thị toast thông báo, reload lại danh sách cảnh báo và cập nhật lại badge summary.
