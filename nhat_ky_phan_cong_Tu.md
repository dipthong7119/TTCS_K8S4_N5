# Nhật ký phân công công việc - Vy Hoàng Tú

**Thành viên:** Vy Hoàng Tú — FE Developer
**Cập nhật mới nhất:** 15/10/2026

---

## Sprint 3-4-5 (cũ) — Hoàn thành 12/10/2026

| Ticket | Mô tả | SP | Trạng thái |
|---|---|---|---|
| SCRUM-61 (FE) | Màn hình khai báo biểu giá | 3 | ✅ Hoàn thành |
| SCRUM-62 (FE) | Màn hình cấu hình khung giờ | 3 | ✅ Hoàn thành |
| SCRUM-208 (FE) | Bảng phân rã chi phí trong modal | 5 (chung) | ✅ Hoàn thành |
| SCRUM-66 (FE) | Modal hoá đơn E-Receipt | 3 (chung) | ✅ Hoàn thành |

---

## Sprint 6-7-8 — Tiến độ (Cập nhật ngày 15/10/2026)

### ✅ SCRUM-96 (FE) — Tài xế tìm trạm gần & xem đầu nối rảnh

**Files tạo mới:**
- [`frontend/templates/driver/station_finder.html`](frontend/templates/driver/station_finder.html)
- [`frontend/static/css/pages/station_finder.css`](frontend/static/css/pages/station_finder.css)
- [`frontend/static/js/pages/station_finder.js`](frontend/static/js/pages/station_finder.js)

**Tính năng đã làm:**
- **SCRUM-241 (subtask):** Thanh thống kê: "X đầu nối rảnh / Y đang sạc / Z trạm / W ngoại tuyến" — cập nhật realtime qua SSE `status_update`.
- **SCRUM-242 (subtask):** Bản đồ Leaflet OSM: marker màu (xanh lá=rảnh, xanh dương=bận, xám=offline), click → popup → drawer chi tiết. Load lazy khi chuyển sang tab bản đồ.
- Chế độ xem thẻ (card grid): mỗi trạm hiển thị chip đầu nối với badge trạng thái (rảnh/sạc/bận/offline) + animation pulse khi rảnh.
- GPS định vị: nút "Vị trí của tôi" → sắp xếp theo khoảng cách Haversine, hiển thị "X.Xkm từ bạn".
- Lọc: tìm theo tên/địa chỉ, lọc trạng thái, sắp xếp (rảnh nhiều nhất / tên / gần nhất).
- Drawer chi tiết: từng trụ → từng đầu nối chip, mini map, nút Google Maps, CTA "Bắt đầu sạc".
- SSE realtime: card cập nhật ngay khi nhận `status_update`, không reload trang.
- Route: `GET /driver/stations` → `require_role("driver")`
- Sidebar: thêm link "Tìm trạm sạc"

**API:** `GET /api/monitoring/tree`, `GET /api/sse`

---

### ✅ SCRUM-98 (FE) — Theo dõi phiên sạc & nhận thông báo (1 SP)

**Files tạo mới:**
- [`frontend/templates/driver/driver_session.html`](frontend/templates/driver/driver_session.html)
- [`frontend/static/css/pages/driver_session.css`](frontend/static/css/pages/driver_session.css)
- [`frontend/static/js/pages/driver_session.js`](frontend/static/js/pages/driver_session.js)

**Tính năng đã làm:**
- **Live card:** kWh nạp, thời gian sạc (live counter đếm giây), ước tính chi phí, số đầu nối.
- **Progress bar:** Ước tính % tiến trình phiên (max 3h).
- **SSE realtime:** Lắng nghe `session_update` → khi phiên kết thúc/bị dừng → overlay fullscreen.
- **Ended overlay:** Popup khi kết thúc — tổng kWh, thời gian, tổng tiền, nút "Xem hoá đơn". Animation scale-in đẹp.
- **Browser Notification:** Xin quyền lúc vào trang, gửi thông báo hệ thống khi phiên kết thúc (kể cả khi tab ẩn).
- **Phiên sạc gần đây:** 5 phiên mới nhất phía dưới.
- **No session state:** Màn hình mời tìm trạm khi không có phiên chạy.
- Route: `GET /driver/session` → `require_role("driver")`
- Sidebar: thêm link "Phiên sạc của tôi"

**API:** `GET /api/sessions/current`, `GET /api/sessions/{id}`, `GET /api/sessions/mine`, `GET /api/sse`

---

### Files đã sửa trong sprint này
| File | Thay đổi |
|---|---|
| `backend/app/routers/pages.py` | Thêm route `/driver/stations` và `/driver/session` |
| `frontend/templates/base.html` | Thêm 2 nav link mới cho driver |
| `frontend/static/js/api_client.js` | Thêm method `findDriverStations()` |

---

### ⏳ Việc còn lại — Chờ BE
| Ticket | Chờ ai | Ghi chú |
|---|---|---|
| SCRUM-80~83 (FE) | Trịnh Thanh Tùng (SM) | BE chưa có model/API công suất — cần field `power_limit` trong Station |
| SCRUM-97 (FE) | Trịnh Thanh Tùng (SM) | Mock SSE đã sẵn trong SCRUM-98; cần chốt payload `session_update` đầy đủ |

### Trạng thái Sprint 678 (15/10/2026)
| Ticket | Mô tả | SP | Trạng thái |
|---|---|---|---|
| SCRUM-96 (FE) | Tìm trạm gần + đầu nối rảnh | subtask FE | ✅ Hoàn thành |
| SCRUM-241 (subtask) | Thống kê đầu nối rảnh | — | ✅ Hoàn thành |
| SCRUM-242 (subtask) | Bản đồ trạm sạc Leaflet | — | ✅ Hoàn thành |
| SCRUM-98 (FE) | Theo dõi phiên sạc + thông báo | 1 SP | ✅ Hoàn thành |
| SCRUM-80~83 (FE) | Giao diện phân bổ công suất | subtask FE | ⏳ Chờ BE (Tùng SM) |
| SCRUM-97 (FE) | Thông báo khi phiên kết thúc | subtask FE | 🔄 Đã mock trong SCRUM-98 |
