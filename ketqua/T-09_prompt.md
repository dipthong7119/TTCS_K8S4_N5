# Yêu cầu thực thi Task T-09 / SCRUM-105: Giao diện danh sách trạm và Form tạo/sửa trạm

**Người thực hiện**: Vy Hoàng Tú
**Mã Jira**: SCRUM-105
**Ngày**: 2026-09-24
**Branch**: VY-TU

---

## Ngữ cảnh (Context)

Dự án CSMS (Nền tảng vận hành trạm sạc xe điện) sử dụng FastAPI (Backend) + HTML/CSS/JS thuần (Frontend). Tài liệu tham chiếu:
- 01_CODEBASE_MAP.md — quy tắc vị trí file
- 02_CODING_STANDARDS.md — quy chuẩn code
- SPRINT_1.md — chi tiết task T-09

**Story S-04**: Là chủ trạm, tôi muốn khai báo trạm sạc để quản lý tài sản của mình.

---

## Nhiệm vụ (Tasks)

Xây dựng Frontend cho task T-09 gồm 3 phần:

### 1. Trang danh sách trạm (giaodien/templates/stations/list.html)
- extends base.html (không copy head)
- 4 thẻ stat: Tổng trạm, Hoạt động (active), Bảo trì (maintenance), Tạm dừng (inactive) — khớp đúng schema stations.status
- Bộ lọc: tìm kiếm text + select trạng thái + nút làm mới
- Bảng: Tên, Địa chỉ, Số trụ, Trạng thái (nhãn chữ + màu), Ngày tạo, Thao tác (Sửa/Xoá)
- Modal xác nhận xoá với cảnh báo rõ ràng
- Loading state (spinner) khi tải
- Phân trang với ellipsis

### 2. Trang form tạo/sửa trạm (giaodien/templates/stations/form.html)
- Dùng lại bố cục từ base.html
- Mode tạo mới: fields Tên (*), Địa chỉ (*), Latitude, Longitude + panel hướng dẫn bước tiếp theo
- Mode sửa: thêm field Trạng thái (active/inactive/maintenance) + bảng trụ sạc hiện có
- Modal thêm trụ với kiểm tra mã trùng real-time khi blur
- Lỗi hiện tại đúng ô nhập — không dùng alert chung chung (02_CODING_STANDARDS 3.3)
- Sau tạo mới → chuyển sang trang edit (không về list) để user thêm trụ ngay

### 3. JS và CSS hỗ trợ
- stations_list.js: tải + render danh sách, stats (đúng status schema), pagination ellipsis, modal xoá + ESC, loading state
- stations_form.js: FormGuard submit, xử lý lỗi 422 từ server, kiểm tra code real-time blur, focus management modal
- stations.css: CSS đặc thù trang (ít hơn 80 dòng)
- api_client.js: thêm checkChargePointCode(code)

---

## Ràng buộc kỹ thuật (từ AC/NFR trong SPRINT_1.md)

| Ràng buộc | Nguồn |
|-----------|-------|
| Form phải chặn bấm lưu 2 lần (FormGuard) | T-09 NFR, SCRUM-105 |
| Lỗi hiện tại đúng ô nhập, không alert chung | T-09 AC, 02_CODING_STANDARDS 3.3 |
| Validate cả phía client VÀ server | T-11 NFR |
| Trạng thái luôn có nhãn chữ kèm màu (không chỉ màu) | 02_CODING_STANDARDS 3.4 |
| Mọi gọi API qua ApiClient, không rải fetch() | 01_CODEBASE_MAP 3 |
| Mọi JS logic nghiệp vụ trong file .js riêng, không inline | 01_CODEBASE_MAP Giới hạn cứng |
| Template phải chạy được ở 360px | 02_CODING_STANDARDS 3.4 |
| Status filter khớp đúng stations.status: active/inactive/maintenance | SPRINT_1.md T-08 Schema |
