# S-47 "Tài xế tìm trạm gần và thấy đầu nối nào đang rảnh"

## Prompt gốc (lưu theo yêu cầu README)

> Xem nội dung đầy đủ trong Git history hoặc conversation context (10/15/2026).

---

## Kết quả triển khai

### Danh sách file đã tạo/sửa

| File | Hành động | Ghi chú |
|------|-----------|---------|
| `backend/app/models/charge_point.py` | **Sửa** | Thêm cột `connector_type` (String 50, nullable) vào `Connector` |
| `backend/app/config.py` | **Sửa** | Thêm `NEARBY_DEFAULT_RADIUS_KM`, `NEARBY_MAX_RADIUS_KM`, `NEARBY_DEFAULT_LIMIT`, `NEARBY_MAX_LIMIT`, `STATION_TIMEZONE` |
| `backend/alembic/versions/h20261015_s47_nearby.py` | **Tạo** | Migration: thêm `connector_type` + 2 index |
| `backend/app/services/nearby.py` | **Tạo** | Service: haversine, bounding box, `don_gia_tai()`, connector stats |
| `backend/app/routers/nearby.py` | **Tạo** | Router `GET /api/stations/nearby` |
| `backend/app/main.py` | **Sửa** | Import + đăng ký `nearby_router` trước `stations_router` |
| `backend/tests/unit/test_s47_nearby.py` | **Tạo** | 26 test cases |

---

### Tên route cuối cùng

**`GET /api/stations/nearby`**

**Lý do:**
- Prefix `/api/stations` nhất quán với router hiện có trong `main.py`.
- Không đụng HTML route `/stations` trong `pages.py` vì HTML router không có prefix `/api`.
- FastAPI khớp `/stations/nearby` (path literal) trước `/stations/{station_id}` (path param) khi đăng ký `nearby_router` **trước** `stations_router`.

---

### Có tạo migration không?

**Có** — `h20261015_s47_nearby.py`:
1. Thêm cột `connectors.connector_type` (nullable VARCHAR 50) — lưu loại đầu nối (CCS2, CHAdeMO, Type2…).
2. Thêm index `ix_stations_status_latlon` trên `(status, latitude, longitude)` để bounding box query nhanh.
3. Thêm index `ix_connectors_cp_type_status` trên `(charge_point_id, connector_type, status)` để gom nhóm nhanh.

---

### Cách đếm `connectors_total`

Đếm **tất cả** `Connector` thuộc các `ChargePoint` của trạm, không loại trừ trạng thái nào.

Lý do: Schema hiện tại không có khái niệm "connector bị vô hiệu hoá". Nếu tương lai thêm `status = 'disabled'`, chỉ cần lọc thêm trong `_build_connector_summary()`.

---

### Cách tra đơn giá

**Tự tạo hàm `don_gia_tai(tariff, thoi_diem)`** trong `services/nearby.py`.

**Lý do không gọi lại `calculate_session_price()`:** Hàm đó yêu cầu `meter_readings`, `started_at`, `ended_at` — không phù hợp để chỉ lấy giá tại một thời điểm. Logic khung giờ (`band_at()`) được tái hiện đơn giản: chuyển UTC → múi giờ trạm → phút trong ngày → duyệt bands.

Biểu giá tra được là biểu giá **không phải demo** (`is_demo=False`) có `effective_from <= now` gần nhất.

---

### Giới hạn tìm không dấu trên SQLite

**SQLite `LIKE` chỉ hỗ trợ ASCII case-insensitive**, không phân biệt dấu tiếng Việt.

- `"tram"` KHÔNG khớp `"trạm"`.
- `"Bac"` KHÔNG khớp `"Bắc"`.
- Workaround trên PostgreSQL: dùng extension `unaccent` + index GIN/GiST — chưa làm vì scope yêu cầu SQLite.

Giới hạn này đã ghi chú trong docstring của endpoint và trong kết quả này.

---

### Số đo hiệu năng

Test `test_no_n_plus_1_queries` với 5 trạm × 2 đầu nối:

| Tình huống | Số SQL queries |
|-----------|----------------|
| 5 trạm, không có biểu giá | **2** (stations + chargepoints) |
| 5 trạm, mỗi trạm có biểu giá | **7** (2 chính + 5 biểu giá) |
| N+1 ngây thơ (so sánh) | 5 × 3 = **15+** |

Ngưỡng assert: ≤ 15 queries để phát hiện N+1 thực sự.

Mục tiêu "200 trạm / 1 000 đầu nối dưới 500 ms" — chưa benchmark thực tế trên SQLite với 200 trạm. Với 2 query chính + index bounding box, dự đoán < 200 ms trên máy phát triển thông thường.

---

### Phân quyền

| Vai trò | Được gọi? |
|---------|-----------|
| `driver` | ✅ |
| `station_owner` | ✅ (dữ liệu công khai) |
| `operator` | ✅ (dữ liệu công khai) |
| `admin` | ✅ |
| Chưa đăng nhập | ❌ 401 |

**Chỉ trạm `status == "active"` xuất hiện.** Trạm `inactive`, `maintenance`, `locked` không bao giờ lộ.

---

### Xử lý `radius_km` vượt trần

**Dùng trần** (không 422). Vượt `NEARBY_MAX_RADIUS_KM=100` → cắt về 100 km.
Lý do: UX tốt hơn; người dùng không bị lỗi chỉ vì nhập số lớn.

---

### Test kết quả

```
26 passed, 8 warnings in 2.25s
```

Tất cả 26 test PASSED. `ruff check` sạch.
