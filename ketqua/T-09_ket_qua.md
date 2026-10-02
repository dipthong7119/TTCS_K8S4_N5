# Kết quả Task T-09 / SCRUM-105: Giao diện danh sách trạm và Form tạo/sửa trạm

**Người thực hiện**: Vy Hoàng Tú
**Mã Jira**: SCRUM-105
**Ngày hoàn thành**: 2026-09-24
**Branch**: VY-TU
**Commit**: feat(T-09/SCRUM-105): Giao dien danh sach tram, form tao/sua tram, ket noi API

---

## Tóm tắt thay đổi

### Acceptance Criteria — Trạng thái

| AC | Kết quả |
|----|---------|
| Tạo, sửa, xem danh sách trạm đều chạy | PASS — kết nối ApiClient.listStations / createStation / updateStation |
| Lỗi nhập liệu hiện ngay tại ô sai | PASS — showFieldError() + data-error attribute |
| Nút lưu bị vô hiệu trong lúc đang gửi | PASS — FormGuard.protect() từ form_guard.js |
| Form gửi đi phải chặn bấm hai lần liên tiếp | PASS — FormGuard |

---

## File đã tạo/chỉnh sửa

### giaodien/templates/stations/list.html
**Thay đổi so với trước:**
- Sửa stat-card từ online/offline → active/inactive/maintenance (khớp đúng schema stations)
- Thêm spinner loading state thay vì text tĩnh
- Thêm aria-live="polite" trên stat values (accessibility)
- Thêm aria-label trên bảng và toàn bộ stat-grid
- Modal xoá: thêm cảnh báo về trụ sạc liên quan bị xoá theo

### giaodien/templates/stations/form.html
**Thay đổi so với trước:**
- Thêm field Trạng thái (select: active/inactive/maintenance) chỉ hiện khi edit
- Thêm panel hướng dẫn bước tiếp theo khi tạo mới (thay vì panel trống)
- Modal thêm trụ: thêm ô hiển thị kết quả check trùng mã real-time (cp-code-check)
- Thêm aria-haspopup, aria-controls cho nút mở modal
- Thêm hint cho connector_count giải thích connectorId OCPP bắt đầu từ 1

### giaodien/static/js/pages/stations_list.js
**Thay đổi so với trước:**
- renderStats(): sửa đúng key active/inactive/maintenance (trước dùng online/offline/charging — sai schema)
- Thêm loading state (spinner + text) khi đang tải dữ liệu
- Thêm error state với empty-state khi API thất bại
- renderPagination(): thêm ellipsis thông minh (không hiện 100 nút trang)
- Modal xoá: thêm ESC để đóng, focus vào nút confirm khi mở, loading state cho nút Xoá
- Thêm try/catch cho fmtDate()

### giaodien/static/js/pages/stations_form.js
**Thay đổi so với trước:**
- Thêm showFieldError() + clearFieldErrors() — hiện lỗi tại đúng ô nhập
- Thêm handleServerErrors() — xử lý lỗi 422 từ FastAPI Pydantic
- Thêm kiểm tra trùng mã trụ real-time khi blur (gọi GET /charge-points/check-code)
- Sau tạo mới → chuyển sang /stations/{id}/edit (thay vì /stations) để thêm trụ ngay
- Modal trụ sạc: thêm focus management (focus vào cp-code khi mở, focus addCpBtn khi đóng)
- Modal trụ sạc: thêm ESC để đóng, loading state cho nút Thêm trụ
- Xử lý lỗi 409 riêng biệt cho mã trụ trùng

### giaodien/static/css/pages/stations.css
**Thêm mới:**
- .form-actions — nút hành động dưới form (justify-content: flex-end)
- .td-address, .td-date — cột bảng danh sách
- .code-tag — hiển thị mã trụ dạng monospace
- .station-guide-card, .guide-steps — panel hướng dẫn
- .spinner + @keyframes spin — loading state
- .pagination__ellipsis — dấu ... phân trang

### giaodien/static/js/api_client.js
**Thêm:**
- checkChargePointCode(code) — GET /charge-points/check-code?code=...

---

## Quy tắc chuẩn đã tuân theo

- Mọi gọi API đi qua ApiClient — không rải fetch() trực tiếp (01_CODEBASE_MAP)
- JS logic nghiệp vụ trong file .js riêng, không inline trong HTML (01_CODEBASE_MAP)
- Trạng thái luôn có nhãn chữ kèm màu (02_CODING_STANDARDS 3.4)
- Template extends base.html (không copy head)
- CSS đặc thù trang < 80 dòng (02_CODING_STANDARDS 3.2)
- FormGuard chặn double submit (02_CODING_STANDARDS 3.3)
- Lỗi hiện tại đúng ô nhập (02_CODING_STANDARDS 3.3)
- Validate cả client VÀ server (T-11 NFR)
- Không tạo file rác, không tạo thư mục ngoài cây (01_CODEBASE_MAP)

---

## Điểm còn phụ thuộc Backend (cần phối hợp với Hoàng Văn Tân)

| Endpoint | Mô tả | Task |
|----------|-------|------|
| GET /stations | Trả list với pagination, filter search+status | T-08 + T-09 |
| POST /stations | Tạo trạm mới, trả về {id, name, ...} | T-09 |
| PUT /stations/{id} | Cập nhật trạm | T-09 |
| DELETE /stations/{id} | Xoá trạm | T-09 |
| GET /charge-points/check-code?code= | Kiểm tra mã trùng: 200 nếu OK, 409 nếu trùng | T-11 |
| POST /charge-points | Tạo trụ sạc mới | T-10 |

**Lưu ý**: Response của GET /stations cần trả về cấu trúc:
```json
{
  "items": [...],
  "total": 42
}
```
Mỗi station item cần có: id, name, address, status, charge_point_count, created_at
