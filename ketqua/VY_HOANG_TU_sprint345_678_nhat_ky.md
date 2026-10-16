# Nhật ký làm việc — Vy Hoàng Tú

**Ngày:** 17/10/2026 | **Sprint:** 345 + 678 | **Người thực hiện:** Vy Hoàng Tú (FE)

---

## ✅ Đã hoàn thành trong phiên này

### 1. Sửa bug nghiêm trọng — `driver_session.js` (SCRUM-98)

**File:** [`frontend/static/js/pages/driver_session.js`](file:///d:/TTCS_K8S4_N5/frontend/static/js/pages/driver_session.js)

**Các bug đã sửa:**
- **Bug 1 — Hàm lồng nhau sai:** `_renderSession`, `_stopDurationTimer`, `_loadCurrentSession`... bị định nghĩa bên trong hàm `_showSession()` → không bao giờ chạy được
- **Bug 2 — Template string lỗi:** Khoảng trắng thừa trong class CSS: `ds - notif - banner--${type}` → `ds-notif-banner--${type}`
- **Bug 3 — Thiếu backtick đóng:** `\`Đầu nối #${session.connector_id}` thiếu dấu đóng
- **Bug 4 — Parse ISO date sai:** Không thêm `'Z'` khi parse chuỗi ISO từ server (server trả naive UTC) → lệch múi giờ
- **Bug 5 — Null guard thiếu:** Các hàm không kiểm tra DOM element tồn tại trước khi thao tác
- **Bug 6 — SSE lệch logic:** Overlay kết thúc hiện cho mọi session, không lọc session của tài xế đang xem

**Sau khi sửa:** SCRUM-98 hoạt động đúng; SCRUM-97 (thông báo kết thúc/dừng qua SSE + browser Notification) hoạt động.

---

### 2. Nâng cấp màn hình khai báo biểu giá (SCRUM-61 FE)

**File:** [`frontend/templates/tariffs/form.html`](file:///d:/TTCS_K8S4_N5/frontend/templates/tariffs/form.html)

**Trước:** Chỉ là mock — `alert(JSON.stringify(...))`, không gọi API.

**Đã làm:**
- Tải danh sách trạm từ `GET /api/stations` → dropdown chọn trạm
- Gọi API thật `POST /api/stations/{id}/tariffs` khi submit
- Thêm field Thời điểm hiệu lực (`datetime-local`)
- Validation phía client: chọn trạm, tên, đơn giá
- Hiển thị thông báo success/error inline (bỏ `alert()`)
- Hỗ trợ `?station_id=...` trên URL để tự chọn trạm sẵn

---

### 3. Nâng cấp màn hình cấu hình khung giờ (SCRUM-62 FE)

**File:** [`frontend/templates/tariffs/time_frames.html`](file:///d:/TTCS_K8S4_N5/frontend/templates/tariffs/time_frames.html)

**Trước:** Validation có nhưng chỉ mock, không kết nối API, không có nhãn band, không visualize.

**Đã làm:**
- **Thanh visualize phủ 24h:** Mỗi khung giờ một màu; khoảng chưa cấu hình hiện kẻ sọc đỏ
- Dropdown chọn trạm → tải biểu giá từ API thật
- Chọn biểu giá đã có → điền bands vào form để tham khảo
- Thêm field Nhãn cho từng khung giờ (VD: "Giờ thấp điểm")
- Giờ kết thúc dùng `<select>` bước 30 phút + tùy chọn 24:00
- Gọi API thật `POST /api/stations/{id}/tariffs` với `bands[]` đầy đủ
- Validation đầy đủ: chồng lấn, khoảng trống, phủ kín 00:00–24:00

---

### 4. Bổ sung API methods — `api_client.js`

**File:** [`frontend/static/js/api_client.js`](file:///d:/TTCS_K8S4_N5/frontend/static/js/api_client.js)

```javascript
listStationTariffs(stationId)              → GET  /stations/{id}/tariffs
createStationTariff(stationId, body)       → POST /stations/{id}/tariffs
getStationPowerCapacity(stationId)         → GET  /stations/{id}/power-capacity
updateStationPowerCapacity(stationId, body)→ PUT  /stations/{id}/power-capacity
getNearbyStations(params)                  → GET  /stations/nearby
```

---

### 5. Xử lý Merge Conflict sau khi pull nhánh `Develop` (PR #100)

- **Giải quyết xung đột trong `api_client.js`**: Tích hợp đồng thời cả Tariffs (SCRUM-61, 62) và Reservations (SCRUM-76 / S-48) từ Develop.
- **Giải quyết xung đột trong `driver_session.js`**: Giữ logic modal Remote Stop, bộ đếm thời gian, kết nối SSE `/api/monitoring/sse` và đồng thời giữ các bản vá an toàn (null guard, timezone handling, filter đúng phiên của tài xế).
- **Kết quả kiểm thử**: Toàn bộ **89/89 tests frontend** (`node tests/frontend_behavior.cjs`) và **774/774 tests backend unit + migration** vượt qua 100%.

---

### 6. Triển khai màn hình Phân bổ công suất trạm (SCRUM-80 FE)

**Files:**
- [`frontend/templates/stations/form.html`](file:///d:/TTCS_K8S4_N5/frontend/templates/stations/form.html)
- [`frontend/static/js/pages/stations_form.js`](file:///d:/TTCS_K8S4_N5/frontend/static/js/pages/stations_form.js)
- [`frontend/static/css/pages/stations.css`](file:///d:/TTCS_K8S4_N5/frontend/static/css/pages/stations.css)

**Đã thực hiện:**
- **Thẻ cấu hình công suất trạm**: Thêm section chuyên biệt `#station-power-card` ngay trong trang chỉnh sửa trạm sạc.
- **Card tóm tắt 3 chỉ số**:
  - Hạn mức trạm (Limit kW)
  - Tổng công suất định danh tất cả đầu nối (Nominal kW = sum of rated_power_kw)
  - Trạng thái phụ tải: Tự động tính toán và hiển thị badge *An toàn (Trong hạn mức)* hoặc *Vượt hạn mức (Over-subscribed)*.
- **Banner cảnh báo Over-subscribed**: Khi công suất định danh vượt hạn mức nguồn cấp trạm, hiển thị cảnh báo giải thích cơ chế phân bổ và điều tiết công suất tự động bảo vệ lưới điện (SCRUM-81 & 82).
- **Bảng khai báo chi tiết từng đầu nối**:
  - Tự động hiển thị toàn bộ đầu nối thuộc các trụ sạc trong trạm
  - Cho phép nhập công suất định danh `rated_power_kw`
  - Các nút chọn nhanh công suất chuẩn: 7.4 kW, 11 kW, 22 kW, 60 kW, 120 kW
- **Kết nối API**: Gọi `GET /api/stations/{id}/power-capacity` để tải và `PUT /api/stations/{id}/power-capacity` để cập nhật kèm audit log.

---

## 📊 Bảng tổng kết trạng thái toàn bộ nhiệm vụ của Vy Hoàng Tú

| Mã Ticket | Tên nhiệm vụ | Loại | Trạng thái |
|---|---|---|---|
| **SCRUM-61** | Khai báo biểu giá trạm theo kWh & phí chiếm trụ | FE | ✅ **HOÀN THÀNH** |
| **SCRUM-62** | Cấu hình biểu giá nhiều khung giờ (24h TOU) | FE | ✅ **HOÀN THÀNH** |
| **SCRUM-63 (208)** | Hiển thị chi tiết cách tính tiền theo từng khung giờ | FE | ✅ **HOÀN THÀNH** (Trong `my_session.js` & hóa đơn) |
| **SCRUM-66** | Màn hình hóa đơn có diễn giải từng đoạn giá | FE | ✅ **HOÀN THÀNH** (Modal E-Receipt nối `/api/sessions/{id}/invoice`) |
| **SCRUM-98** | Theo dõi phiên sạc thời gian thực + nhận SSE | FE / Story | ✅ **HOÀN THÀNH** (89/89 tests pass) |
| **SCRUM-97** | Thông báo khi phiên kết thúc hoặc bị dừng | FE | ✅ **HOÀN THÀNH** (Browser Notification + Overlay) |
| **SCRUM-96 (241, 242)** | Tìm trạm gần & đếm đầu nối rảnh | FE | ✅ **HOÀN THÀNH** (Trong `station_finder.js` + bản đồ Leaflet) |
| **SCRUM-80** | Đặt hạn mức công suất trạm & từng đầu nối | FE | ✅ **HOÀN THÀNH** (Form cấu hình công suất + Over-subscribed) |

---

## 👥 Ghi chú cho reviewer (Đặng Ngọc Đại)

- Review `driver_session.js`: Kiểm tra chạy mượt mà với API và SSE từ `Develop`.
- Review `stations_form.js` & `form.html`: Kiểm tra card cấu hình công suất trạm, tính toán tải danh định và trạng thái Over-subscribed.
- Chạy kiểm thử: `node tests/frontend_behavior.cjs` (89/89 passed).

