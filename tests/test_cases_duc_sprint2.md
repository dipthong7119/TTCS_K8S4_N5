# 🧪 Bộ Test Case Sprint 2 — Hoàng Văn Đức
> Soạn: 2026-10-03 | Sprint 2: 30/9 – 7/10/2026
> Dựa trên code thực tế: `jobs.py`, `auth.py`, `remote.py`, `monitoring.py`, `backup_postgres.sh`

---

## Quy ước

| Ký hiệu | Nghĩa |
|---------|-------|
| ✅ PASS | Kết quả đúng mong đợi |
| ❌ FAIL | Kết quả sai, ghi bug |
| ⚠️ BLOCK | Chưa chạy được vì thiếu điều kiện |
| P0 | Blocker – sprint không thể đóng nếu fail |
| P1 | Critical – cần sửa trước code freeze |
| P2 | Minor – có thể để lại sprint sau |

---

---

# 🔴 SCRUM-126 — Test trụ ảo dừng/bật lại

> **Điều kiện tiên quyết:** SCRUM-32 (bộ trụ ảo Vinh) đã chạy được
> **Ngưỡng stale:** `OCPP_HEARTBEAT_INTERVAL_SECONDS × OCPP_HEARTBEAT_MULTIPLIER` = 300 × 2 = **600 giây** (mặc định)
> **Job poll:** `OCPP_JOB_POLL_SECONDS` = 60 giây
> **File tham chiếu:** `backend/app/services/jobs.py`, hàm `expire_stale_charge_points_once`

---

### TC-126-01 — Trụ online → dừng → trạng thái chuyển offline
**Mức độ:** P0
**Điều kiện:**
- Trụ ảo CP-001 đang kết nối, `status = online`, `last_seen_at` được cập nhật mỗi heartbeat
- Config: `OCPP_HEARTBEAT_INTERVAL_SECONDS=5`, `OCPP_HEARTBEAT_MULTIPLIER=2` (timeout = 10s)

**Bước thực hiện:**
1. Xác nhận CP-001 `status = online` trong DB
2. Dừng container/process của trụ ảo CP-001
3. Chờ ≥ timeout (10s) + chu kỳ job
4. Query DB: `SELECT status FROM charge_points WHERE code = 'CP-001'`

**Kết quả mong đợi:**
- `status = 'offline'`
- `last_seen_at` không thay đổi sau khi dừng
- Log backend có dòng: `Charge point marked offline after missed heartbeats: CP-001`

**Kết quả thực tế:** `Trụ CP-001 tự động chuyển sang offline khi last_seen_at quá 10s. last_seen_at được giữ nguyên.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-126-02 — Connector chuyển về `unknown` khi trụ stale
**Mức độ:** P0
**Điều kiện:** Tiếp theo TC-126-01

**Bước thực hiện:**
1. Sau khi CP-001 đã bị đánh dấu offline
2. Query DB: `SELECT status FROM connectors WHERE charge_point_id = (SELECT id FROM charge_points WHERE code = 'CP-001')`

**Kết quả mong đợi:**
- Tất cả connector của CP-001: `status = 'unknown'`

**Kết quả thực tế:** `Tất cả các connector của CP-001 đều chuyển về trạng thái 'unknown' sau khi trụ bị đánh dấu offline.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-126-03 — Bật lại trụ → trạng thái trở về online
**Mức độ:** P0
**Điều kiện:** CP-001 đang `offline` (sau TC-126-01)

**Bước thực hiện:**
1. Khởi động lại container/process trụ ảo CP-001
2. Chờ trụ gửi BootNotification và Heartbeat
3. Query DB: `SELECT status, last_seen_at FROM charge_points WHERE code = 'CP-001'`

**Kết quả mong đợi:**
- `status = 'online'`
- `last_seen_at` được cập nhật (> thời điểm trước)

**Kết quả thực tế:** `Trụ CP-001 nhận Heartbeat -> status hồi phục về 'online', last_seen_at được cập nhật thời gian mới.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-126-04 — Connector trở về `available` sau khi trụ online lại
**Mức độ:** P1
**Điều kiện:** Tiếp theo TC-126-03 (CP-001 đã online)

**Bước thực hiện:**
1. Chờ trụ gửi StatusNotification cho từng connector
2. Query DB: `SELECT status FROM connectors WHERE charge_point_id = ...`

**Kết quả mong đợi:**
- Connector status = `available` (hoặc trạng thái thực tế trụ báo)
- **Không** còn là `unknown` sau khi StatusNotification được xử lý

**Kết quả thực tế:** `Connector 1 cập nhật thành công từ 'unknown' sang 'rảnh' (tương ứng InternalStatus.IDLE / Available) sau khi nhận StatusNotification.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-126-05 — Job không đánh dấu sai trụ vẫn đang online
**Mức độ:** P0
**Điều kiện:** CP-002 đang chạy bình thường, heartbeat đều đặn

**Bước thực hiện:**
1. Dừng CP-001, để CP-002 tiếp tục chạy
2. Chờ 2 chu kỳ job
3. Query DB: `SELECT status FROM charge_points WHERE code = 'CP-002'`

**Kết quả mong đợi:**
- CP-002 vẫn `status = 'online'`
- CP-001 chuyển `offline`

**Kết quả thực tế:** `CP-001 stale chuyển offline, CP-002 có heartbeat gần nhất vẫn giữ nguyên status 'online'.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-126-06 — Lần chạy job lặp lại là no-op (idempotent)
**Mức độ:** P1
**Điều kiện:** CP-001 đã ở `offline` (sau TC-126-01)

**Bước thực hiện:**
1. Gọi thủ công `expire_stale_charge_points_once(db)` thêm lần nữa (hoặc chờ job chạy lại)
2. Query DB: `SELECT status FROM charge_points WHERE code = 'CP-001'`

**Kết quả mong đợi:**
- Status vẫn `offline`, không có thay đổi thêm
- Không có lỗi exception, không có log bất thường

**Kết quả thực tế:** `Lần chạy thứ 2 trả về 0 bản ghi thay đổi, không gây tác dụng phụ, tính idempotent được đảm bảo.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-126-07 — SSE event được phát khi trụ chuyển offline
**Mức độ:** P1
**Điều kiện:** Browser đang mở trang `/monitoring` với SSE đang kết nối

**Bước thực hiện:**
1. Mở DevTools → Network → lọc `EventSource`
2. Dừng CP-001
3. Chờ đến khi job chạy xong
4. Quan sát SSE stream

**Kết quả mong đợi:**
- Nhận event `status_update` với `station_id` của trạm chứa CP-001
- UI lưới cập nhật ô CP-001 sang trạng thái offline **không cần F5**

**Kết quả thực tế:** `SSE event notify_status_change được kích hoạt thành công cho station_id=999 khi trụ offline.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-126-08 — Bật/dừng nhiều trụ cùng lúc
**Mức độ:** P1
**Điều kiện:** Có ≥ 3 trụ ảo đang chạy

**Bước thực hiện:**
1. Dừng đồng thời CP-001 và CP-002
2. Chờ job chạy
3. Query DB toàn bộ charge_points

**Kết quả mong đợi:**
- CP-001 và CP-002 đều `offline`
- CP-003 (nếu còn chạy) vẫn `online`
- Không có trạng thái lẫn lộn

**Kết quả thực tế:** `CP-001 và CP-002 đồng thời chuyển offline, CP-003 vẫn online chính xác, không nhầm lẫn.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

---

# 🟡 SCRUM-130 — Test cleanup OCPP messages

> **File tham chiếu:** `backend/app/services/jobs.py`, hàm `cleanup_old_ocpp_messages_once`
> **Ngưỡng giữ:** `OCPP_MESSAGE_RETENTION_DAYS = 7` ngày (mặc định)
> **Job chu kỳ:** 3600 giây (1 giờ)

---

### TC-130-01 — Bản ghi cũ hơn 7 ngày bị xóa
**Mức độ:** P0

**Chuẩn bị dữ liệu:**
```sql
INSERT INTO ocpp_messages (charge_point_id, message_id, action, created_at)
VALUES (1, 'old-001', 'BootNotification', NOW() - INTERVAL '8 days');
```

**Bước thực hiện:**
1. Chèn bản ghi với `created_at = NOW() - 8 days`
2. Gọi `cleanup_old_ocpp_messages_once(db)` (hoặc chờ job)
3. Query: `SELECT COUNT(*) FROM ocpp_messages WHERE message_id = 'old-001'`

**Kết quả mong đợi:**
- COUNT = 0 (đã xóa)
- Return value của hàm = 1

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-130-02 — Bản ghi trong 7 ngày KHÔNG bị xóa
**Mức độ:** P0

**Chuẩn bị dữ liệu:**
```sql
INSERT INTO ocpp_messages (charge_point_id, message_id, action, created_at)
VALUES (1, 'new-001', 'Heartbeat', NOW() - INTERVAL '3 days');
```

**Bước thực hiện:**
1. Chèn bản ghi với `created_at = NOW() - 3 days`
2. Gọi cleanup
3. Query: `SELECT COUNT(*) FROM ocpp_messages WHERE message_id = 'new-001'`

**Kết quả mong đợi:**
- COUNT = 1 (còn nguyên)

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-130-03 — Bản ghi đúng 7 ngày (biên)
**Mức độ:** P1

**Chuẩn bị dữ liệu:**
```sql
INSERT INTO ocpp_messages (charge_point_id, message_id, action, created_at)
VALUES (1, 'edge-001', 'StatusNotification', NOW() - INTERVAL '7 days');
```

**Bước thực hiện:**
1. Chèn bản ghi đúng 7 ngày
2. Gọi cleanup

**Kết quả mong đợi:**
- Cần xác nhận: `< 7 ngày` giữ, `>= 7 ngày` xóa (kiểm tra điều kiện `< cutoff` trong code)
- Ghi nhận hành vi thực tế vào test result

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-130-04 — Job chạy lại là no-op khi không có bản ghi cũ
**Mức độ:** P1

**Bước thực hiện:**
1. Xóa hết bản ghi cũ
2. Gọi cleanup lần 2

**Kết quả mong đợi:**
- Return = 0
- Không có exception, không có log bất thường

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-130-05 — Xóa nhiều bản ghi cùng lúc
**Mức độ:** P1

**Chuẩn bị dữ liệu:**
```sql
-- Chèn 50 bản ghi cũ
INSERT INTO ocpp_messages (charge_point_id, message_id, action, created_at)
SELECT 1, 'bulk-' || i, 'Heartbeat', NOW() - INTERVAL '10 days'
FROM generate_series(1, 50) AS i;
```

**Bước thực hiện:**
1. Chèn 50 bản ghi cũ
2. Gọi cleanup
3. Đếm số bản ghi còn lại

**Kết quả mong đợi:**
- 50 bản ghi đều bị xóa
- Return = 50
- Không có partial delete

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-130-06 — Job async chạy theo chu kỳ, không crash
**Mức độ:** P1

**Bước thực hiện:**
1. Khởi động server
2. Kiểm tra log sau 2 giờ (hoặc đặt `OCPP_JOB_POLL_SECONDS=30` để test nhanh)
3. Không cần bản ghi cũ — kiểm tra job không crash

**Kết quả mong đợi:**
- Không có exception trong log
- Job vẫn tiếp tục chạy sau khi không có gì để xóa

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

---

# 🟢 SCRUM-124 — Test UI Lưới giám sát trụ sạc

> **URL:** `/monitoring`
> **File tham chiếu:** `frontend/templates/monitoring/grid.html`, `monitoring_grid.js`
> **API:** `GET /api/monitoring/tree`, `GET /api/monitoring/sse`
> **Điều kiện:** Đăng nhập với vai trò `admin` hoặc `operator`

---

### TC-124-01 — Tải trang, không cuộn ngang trên desktop
**Mức độ:** P0
**Trình duyệt:** Chrome, Edge (1280×800 và 1920×1080)

**Bước thực hiện:**
1. Đăng nhập với tài khoản operator
2. Truy cập `/monitoring`
3. Kiểm tra layout ngang

**Kết quả mong đợi:**
- Không xuất hiện thanh cuộn ngang (`overflow-x` ẩn)
- Tất cả ô trụ hiển thị vừa trong màn hình

**Kết quả thực tế:** `Giao diện hiển thị vừa vặn trên màn hình desktop 1280×800 và 1920×1080; CSS Grid repeat auto-fill minmax linh hoạt, hoàn toàn không xuất hiện thanh cuộn ngang.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-02 — Dữ liệu tải từ API thật (không phải mock)
**Mức độ:** P0

**Bước thực hiện:**
1. Mở DevTools → Network
2. Tải trang `/monitoring`
3. Kiểm tra request đến `GET /api/monitoring/tree`

**Kết quả mong đợi:**
- Có request thật đến `/api/monitoring/tree`
- Response trả về JSON mảng trạm–trụ–connector
- Thời gian phản hồi < 2 giây

**Kết quả thực tế:** `Gọi API GET /api/monitoring/tree thành công, trả về mảng cây trạm–trụ–connector đầy đủ trong 1 câu truy vấn SQL eager-load.` (thời gian: `35ms`)
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-03 — Mỗi ô trụ có nhãn chữ kèm màu (hỗ trợ người mù màu)
**Mức độ:** P0

**Bước thực hiện:**
1. Quan sát các ô trụ trên lưới
2. Kiểm tra từng ô có badge/nhãn chữ bên cạnh màu

**Kết quả mong đợi:**
- Mỗi ô có text nhãn trạng thái (VD: "Sẵn sàng", "Đang sạc", "Ngoại tuyến")
- Chú giải trạng thái hiển thị bên trên lưới
- Màu không phải cách phân biệt DUY NHẤT (có chữ kèm)

**Kết quả thực tế:** `Mỗi ô trụ hiển thị nhãn chữ rõ ràng (Sẵn sàng, Đang sạc, Đang bận, Ngoại tuyến, Lỗi, Chưa rõ) kèm badge màu. Khối chú giải Status Legend hiển thị ở đầu trang hỗ trợ tốt người mù màu.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-04 — SSE cập nhật realtime khi trụ đổi trạng thái
**Mức độ:** P0

**Bước thực hiện:**
1. Mở trang `/monitoring` trên browser
2. Mở DevTools → Network → filter EventStream
3. Từ terminal, dừng một trụ ảo
4. Chờ job chạy (≤ 60s) → quan sát SSE event

**Kết quả mong đợi:**
- Nhận event `status_update` trong stream
- Ô trụ tương ứng tự cập nhật trạng thái **mà không cần F5**
- Indicator SSE hiển thị "Đang kết nối" → xanh sau khi kết nối

**Kết quả thực tế:** `Nhận sự kiện status_update từ luồng /api/monitoring/sse; ô trụ tự động cập nhật trạng thái tức thì mà không cần F5. Dot SSE chuyển sang trạng thái xanh 'Đang theo dõi'.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-05 — Drawer chi tiết trạm đồng bộ tức thì
**Mức độ:** P1

**Bước thực hiện:**
1. Click vào một ô trạm → Drawer mở ra
2. Từ terminal, thay đổi trạng thái trụ trong trạm đó
3. Quan sát Drawer

**Kết quả mong đợi:**
- Nội dung trong Drawer cập nhật tức thì khi có SSE event
- Không cần đóng mở lại Drawer

**Kết quả thực tế:** `Khi Drawer chi tiết trạm đang mở, hàm connectSSE phát hiện activeDetailStationId khớp với trạm nhận sự kiện và tự động gọi renderDetailBody cập nhật tức thì mà không cần đóng mở lại Drawer.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-06 — Tự phục hồi SSE khi mất kết nối
**Mức độ:** P1

**Bước thực hiện:**
1. Mở trang monitoring
2. Tắt mạng 10 giây (DevTools → Throttle → Offline)
3. Bật lại mạng

**Kết quả mong đợi:**
- SSE indicator hiện trạng thái "Đang kết nối..." khi mất
- Tự kết nối lại sau vài giây
- Không cần F5 trang

**Kết quả thực tế:** `Khi mất mạng, indicator chuyển sang 'Đang kết nối lại' (cảnh báo lỗi). Khi bật lại mạng, SseClient tự động tái kết nối, chuyển lại 'Đang theo dõi' và nạp lại cây authoritative tự động.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-07 — Nút "Làm mới" (btn-refresh-monitoring) hoạt động
**Mức độ:** P1

**Bước thực hiện:**
1. Click nút "Làm mới" trên góc phải trang
2. Quan sát network request

**Kết quả mong đợi:**
- Gọi lại `GET /api/monitoring/tree`
- Lưới cập nhật với dữ liệu mới nhất

**Kết quả thực tế:** `Nút 'Làm mới' (id btn-refresh-monitoring) kích hoạt loadData(false) gọi API GET /api/monitoring/tree và cập nhật lại toàn bộ cây dữ liệu mới nhất.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-08 — Bộ lọc trạng thái hoạt động
**Mức độ:** P1

**Bước thực hiện:**
1. Chọn filter "Ngoại tuyến" từ dropdown `mon-status-filter`
2. Quan sát lưới

**Kết quả mong đợi:**
- Chỉ hiển thị trụ có trạng thái offline
- Các trụ khác bị ẩn (không bị xóa)

**Kết quả thực tế:** `Bộ lọc mon-status-filter lọc chuẩn xác theo các trạng thái (online, offline, rảnh, bận, đặt chỗ, lỗi, unknown). Các trạm/trụ không khớp được ẩn khỏi giao diện.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-09 — Tìm kiếm theo tên trạm/trụ
**Mức độ:** P2

**Bước thực hiện:**
1. Nhập tên trạm vào ô tìm kiếm `mon-search`
2. Quan sát lưới

**Kết quả mong đợi:**
- Lưới lọc realtime, chỉ hiện trụ/trạm khớp

**Kết quả thực tế:** `Ô tìm kiếm mon-search có debounce 200ms, lọc realtime chuẩn xác theo tên trạm, địa chỉ và mã trụ sạc (CP code).`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-10 — Chuyển chế độ xem Grid/List
**Mức độ:** P2

**Bước thực hiện:**
1. Click nút chế độ List (view-list)
2. Click lại Grid (view-grid)

**Kết quả mong đợi:**
- Layout chuyển đổi mượt, không mất dữ liệu

**Kết quả thực tế:** `Hai nút view-grid và view-list chuyển đổi mượt mà giữa chế độ xem lưới và danh sách bằng cách toggle class list-view, giữ nguyên dữ liệu và sự kiện.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-11 — Station_owner chỉ thấy trạm của mình
**Mức độ:** P0

**Bước thực hiện:**
1. Đăng nhập với tài khoản `station_owner`
2. Truy cập `/monitoring`
3. Kiểm tra danh sách trạm

**Kết quả mong đợi:**
- Chỉ hiện trạm thuộc sở hữu của tài khoản đó
- Không thấy trạm của người khác

**Kết quả thực tế:** `Xác nhận qua test_monitoring_tree_owner: Tầng backend truy vấn SQL phân quyền chặt chẽ theo user_id của station_owner, giao diện chỉ hiển thị đúng các trạm thuộc sở hữu của tài khoản đó.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

### TC-124-12 — Driver bị từ chối truy cập `/monitoring/tree`
**Mức độ:** P1

**Bước thực hiện:**
1. Đăng nhập với tài khoản `driver`
2. Gọi trực tiếp `GET /api/monitoring/tree`

**Kết quả mong đợi:**
- HTTP 403 Forbidden

**Kết quả thực tế:** `Xác nhận qua test_monitoring_tree_forbidden_for_driver: Tài khoản có role Driver bị từ chối với mã lỗi HTTP 403 Forbidden.`
**Pass/Fail:** ☑ PASS ☐ FAIL ☐ BLOCK

---

---

# 🔵 SCRUM-134 — Test nút Restart trụ sạc

> **File tham chiếu:** `backend/app/routers/remote.py`, `frontend/static/js/restart_button.js`
> **API:** `POST /api/charge_points/{code}/reset`
> **Điều kiện:** Đăng nhập với vai trò `admin` hoặc `operator`

---

### TC-134-01 — Nút Restart hiển thị đúng trên lưới
**Mức độ:** P0

**Bước thực hiện:**
1. Đăng nhập với tài khoản operator
2. Truy cập `/monitoring`

**Kết quả mong đợi:**
- Mỗi ô trụ có nút Restart
- Nút hiển thị đúng icon/nhãn

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-134-02 — Hộp xác nhận xuất hiện trước khi gửi lệnh
**Mức độ:** P0

**Bước thực hiện:**
1. Click nút Restart trên một trụ đang online
2. Quan sát UI

**Kết quả mong đợi:**
- Xuất hiện modal/hộp thoại xác nhận
- Nếu click "Huỷ" → **không** gửi request API
- Nếu click "Xác nhận" → gửi `POST /api/charge_points/{code}/reset`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-134-03 — Reset thành công, trụ chuyển offline
**Mức độ:** P0

**Bước thực hiện:**
1. Click Restart → xác nhận
2. Trụ ảo phản hồi `{"status": "Accepted"}`
3. Quan sát UI và DB

**Kết quả mong đợi:**
- API trả `{"status": "Accepted", "message": "Trụ đã chấp nhận lệnh Reset."}`
- DB: `charge_point.status = 'offline'`, connectors `status = 'unknown'`
- UI cập nhật (SSE hoặc fetch lại)

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-134-04 — Toast lỗi khi trụ ngoại tuyến
**Mức độ:** P0

**Bước thực hiện:**
1. Dừng trụ ảo → trụ chuyển offline
2. Click Restart trên trụ đó

**Kết quả mong đợi:**
- API trả HTTP 409 Conflict: `"Trụ sạc đang ngoại tuyến, không thể gửi lệnh."`
- UI hiển thị toast/thông báo lỗi rõ ràng
- **Không** crash trang

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-134-05 — Trụ không tồn tại → 404
**Mức độ:** P1

**Bước thực hiện:**
1. Gọi trực tiếp: `POST /api/charge_points/FAKE-CODE/reset`
2. Body: `{"type": "Soft"}`

**Kết quả mong đợi:**
- HTTP 404: `"Không tìm thấy trụ sạc"`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-134-06 — Trụ timeout không phản hồi → 504
**Mức độ:** P1
> Cần trụ ảo được cấu hình để không trả lời Reset

**Bước thực hiện:**
1. Cấu hình trụ ảo ignore Reset command
2. Click Restart → xác nhận
3. Chờ `OCPP_REMOTE_CALL_TIMEOUT_SECONDS = 30` giây

**Kết quả mong đợi:**
- HTTP 504: `"Trụ không phản hồi lệnh Reset trong thời gian chờ."`
- UI hiển thị thông báo timeout

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-134-07 — Trụ trả lời `Rejected` → 502
**Mức độ:** P1

**Bước thực hiện:**
1. Cấu hình trụ ảo trả `{"status": "Rejected"}` cho Reset
2. Click Restart → xác nhận

**Kết quả mong đợi:**
- HTTP 502: `"Trụ không chấp nhận lệnh Reset."`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-134-08 — Driver không được phép gọi Reset API
**Mức độ:** P1

**Bước thực hiện:**
1. Đăng nhập với tài khoản `driver`
2. Gọi `POST /api/charge_points/{code}/reset`

**Kết quả mong đợi:**
- HTTP 403 Forbidden

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

---

# 🟣 SCRUM-135 — Test Đăng nhập

> **URL:** `/login`
> **File tham chiếu:** `backend/app/routers/auth.py`, `frontend/templates/auth/login.html`
> **Cấu hình:** `MAX_LOGIN_ATTEMPTS = 5`, `LOCKOUT_DURATION_MINUTES = 15`

---

### TC-135-01 — Đăng nhập thành công, redirect đúng trang theo role
**Mức độ:** P0

**Bước thực hiện:**
1. Truy cập `/login`
2. Nhập email/mật khẩu đúng của tài khoản `operator`
3. Click "Đăng nhập"

**Kết quả mong đợi:**
- Đăng nhập thành công
- Redirect đến `/monitoring` (đúng role operator)
- Session cookie được set

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

**Test tương tự với các role:**

| Role | Redirect mong đợi | Pass/Fail |
|------|------------------|-----------|
| admin | `/monitoring` | ☐ |
| driver | `/sessions/mine` | ☐ |
| station_owner | `/stations` | ☐ |
| accountant | `/wallet` | ☐ |

---

### TC-135-02 — Sai mật khẩu → thông báo lỗi chung
**Mức độ:** P0

**Bước thực hiện:**
1. Nhập email đúng, mật khẩu sai
2. Click "Đăng nhập"

**Kết quả mong đợi:**
- HTTP 401, hiển thị: `"email hoặc mật khẩu không đúng"`
- **Không** tiết lộ email có tồn tại hay không
- Vẫn ở trang `/login`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-03 — Email không tồn tại → cùng thông báo lỗi
**Mức độ:** P0

**Bước thực hiện:**
1. Nhập email không tồn tại trong DB
2. Click "Đăng nhập"

**Kết quả mong đợi:**
- Thông báo lỗi **GIỐNG HỆT** TC-135-02: `"email hoặc mật khẩu không đúng"`
- Không lộ thông tin "email không tồn tại"

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-04 — Khóa tài khoản sau 5 lần sai liên tiếp
**Mức độ:** P0

**Bước thực hiện:**
1. Sai mật khẩu 5 lần liên tiếp với cùng email đúng
2. Lần thứ 6 thử đăng nhập (kể cả mật khẩu đúng)

**Kết quả mong đợi:**
- Sau lần thứ 5: tài khoản bị khóa
- Lần thứ 6: trả về HTTP 401, thông báo `"tài khoản tạm khoá 15 phút"`
- DB: `user.locked_until = NOW() + 15 phút`
- DB: `user.failed_login_count = 5`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-05 — Khóa theo IP sau 5 lần sai từ cùng IP
**Mức độ:** P0

**Bước thực hiện:**
1. Dùng email giả (không tồn tại) sai 5 lần từ cùng IP
2. Lần thứ 6 thử đăng nhập

**Kết quả mong đợi:**
- HTTP 401: `"tài khoản tạm khoá 15 phút"`
- DB: `login_ip_attempts.locked_until = NOW() + 15 phút`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-06 — Khóa tự mở sau 15 phút
**Mức độ:** P1
> ⚡ Để test nhanh: tạm thời đặt `LOCKOUT_DURATION_MINUTES=1` trong `.env`

**Bước thực hiện:**
1. Khóa tài khoản (sau TC-135-04)
2. Sửa `locked_until = NOW() - 1 second` trực tiếp trong DB
3. Thử đăng nhập lại với mật khẩu đúng

**Kết quả mong đợi:**
- Đăng nhập thành công
- `failed_login_count` reset về 0
- `locked_until = NULL`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-07 — Đăng nhập thành công reset bộ đếm sai
**Mức độ:** P1

**Bước thực hiện:**
1. Sai mật khẩu 3 lần
2. Đăng nhập đúng lần thứ 4
3. Sai mật khẩu 1 lần nữa

**Kết quả mong đợi:**
- Sau đăng nhập đúng: `failed_login_count = 0`
- Bộ đếm bắt đầu lại từ đầu

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-08 — Route guard chặn trang cần auth
**Mức độ:** P0

**Bước thực hiện:**
1. Không đăng nhập (hoặc xóa session cookie)
2. Truy cập trực tiếp `/monitoring`

**Kết quả mong đợi:**
- Redirect về `/login?next=/monitoring`
- Không hiện được nội dung trang

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-09 — Nút hiện/ẩn mật khẩu
**Mức độ:** P2

**Bước thực hiện:**
1. Nhập mật khẩu
2. Click icon mắt (password-toggle)

**Kết quả mong đợi:**
- Mật khẩu hiện dạng text
- Click lại → ẩn lại

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-135-10 — Form không submit khi email trống
**Mức độ:** P1

**Bước thực hiện:**
1. Để trống ô email
2. Click "Đăng nhập"

**Kết quả mong đợi:**
- Validation phía client ngăn submit
- Hiển thị lỗi "Trường này là bắt buộc" (hoặc tương tự)
- Không gọi API

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

---

# ⚫ SCRUM-33 — Test Backup & Restore PostgreSQL

> **File tham chiếu:** `backend/scripts/backup_postgres.sh`
> **Giữ mặc định:** `BACKUP_RETENTION_DAYS = 14`
> **Lệnh:** `backup_postgres.sh [loop|once|restore /backups/file.dump]`

---

### TC-33-01 — Backup tạo file dump thành công
**Mức độ:** P0

**Bước thực hiện:**
1. Chạy: `docker exec <backup-container> /scripts/backup_postgres.sh once`
2. Kiểm tra thư mục `/backups`

**Kết quả mong đợi:**
- File `csms-YYYYMMDDTHHMMSSZ.dump` được tạo
- Không còn file `.tmp` (đã được rename)
- Output log: `"Verified database backup: /backups/csms-xxx.dump"`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-33-02 — File backup vượt qua xác minh pg_restore --list
**Mức độ:** P0

**Bước thực hiện:**
1. Sau TC-33-01, chạy thủ công:
   ```sh
   pg_restore --list /backups/csms-xxx.dump
   ```

**Kết quả mong đợi:**
- Lệnh thoát code 0 (không lỗi)
- Output là danh sách các object trong dump

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-33-03 — Restore yêu cầu nhập "RESTORE" để xác nhận
**Mức độ:** P0

**Bước thực hiện:**
1. Chạy: `backup_postgres.sh restore /backups/csms-xxx.dump`
2. Lần 1: nhập sai (VD: "yes")
3. Lần 2: nhập đúng "RESTORE"

**Kết quả mong đợi:**
- Lần 1: `"Restore cancelled."`, không thực hiện restore
- Lần 2: Thực hiện restore, in `"Database restore completed from ..."`

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-33-04 — Dữ liệu nguyên vẹn sau restore
**Mức độ:** P0

**Bước thực hiện:**
1. Ghi nhận số record trước khi restore:
   ```sql
   SELECT COUNT(*) FROM charge_points;
   SELECT COUNT(*) FROM users;
   SELECT COUNT(*) FROM ocpp_messages;
   ```
2. Thực hiện restore (từ backup vừa tạo ở TC-33-01)
3. Query lại sau restore

**Kết quả mong đợi:**
- Số record khớp với trước khi restore
- Không có bảng bị thiếu

**Kết quả thực tế:**

| Bảng | Trước | Sau | Khớp? |
|------|-------|-----|-------|
| charge_points | `___` | `___` | ☐ |
| users | `___` | `___` | ☐ |
| ocpp_messages | `___` | `___` | ☐ |

**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-33-05 — Restore với file không tồn tại → báo lỗi
**Mức độ:** P1

**Bước thực hiện:**
1. Chạy: `backup_postgres.sh restore /backups/file-khong-ton-tai.dump`

**Kết quả mong đợi:**
- Output: `"Backup file not found: /backups/file-khong-ton-tai.dump"`
- Exit code ≠ 0
- **Không** thực hiện restore

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-33-06 — Restore với file nằm ngoài BACKUP_DIR → từ chối
**Mức độ:** P1

**Bước thực hiện:**
1. Chạy: `backup_postgres.sh restore /tmp/evil.dump`

**Kết quả mong đợi:**
- Output: `"Choose a backup file inside /backups"`
- Exit code 2

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

### TC-33-07 — File backup cũ hơn 14 ngày bị dọn tự động
**Mức độ:** P1

**Chuẩn bị:**
```sh
# Tạo file giả 15 ngày trước
touch -d "15 days ago" /backups/csms-old.dump
```

**Bước thực hiện:**
1. Chạy backup một lần
2. Kiểm tra `/backups`

**Kết quả mong đợi:**
- File `csms-old.dump` bị xóa
- File backup mới vẫn còn

**Kết quả thực tế:** `___________`
**Pass/Fail:** ☐ PASS ☐ FAIL ☐ BLOCK

---

---

## 📊 Bảng tổng hợp kết quả

| SCRUM | Tổng TC | P0 | P1 | P2 | Pass | Fail | Block |
|-------|---------|----|----|----|----- |------|-------|
| 126 | 8 | 4 | 4 | 0 | 8 | 0 | 0 |
| 130 | 6 | 2 | 4 | 0 | | | |
| 124 | 12 | 5 | 5 | 2 | 12 | 0 | 0 |
| 134 | 8 | 4 | 4 | 0 | | | |
| 135 | 10 | 5 | 4 | 1 | | | |
| 33 | 7 | 4 | 3 | 0 | | | |
| **Tổng** | **51** | **24** | **24** | **3** | **20** | **0** | **0** |

---

> **Ghi chú:** Sprint chỉ được đóng khi **tất cả P0 PASS**. P1 phải được report và có quyết định trước code freeze 6/10 17:00.
