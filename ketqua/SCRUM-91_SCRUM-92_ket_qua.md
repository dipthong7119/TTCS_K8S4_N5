# Báo cáo kết quả thực hiện SCRUM-91 & SCRUM-92 (Frontend)

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)  
**Vai trò:** Frontend Developer (Sprint 6-7-8)  
**Epic:** Giám sát vận hành / Quản trị hệ thống & Bảo vệ dữ liệu  
**Story SCRUM-91:** S-56 — Nhật ký thao tác trên giao dịch ví truy được ai làm gì (3 SP)  
**Story SCRUM-92:** S-57 — Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển theo Nghị định 13/2023/NĐ-CP (3 SP)  
**Người phối hợp Backend:** Hoàng Văn Đức  
**Reviewer:** Vy Hoàng Tú / Trịnh Thanh Tùng  
**Trạng thái:** Hoàn tất 100% triển khai Frontend, Đăng ký Route & Sẵn sàng nghiệm thu  

---

## PHẦN 1: SCRUM-91 — NHẬT KÝ THAO TÁC TRÊN GIAO DỊCH VÍ (S-56)

### 1.1 Mục tiêu & Tiêu chí nghiệm thu (Acceptance Criteria)
- **User Story:** Là quản trị hệ thống tôi muốn truy được ai đã nạp tay, ai đã điều chỉnh ví nào lúc nào để điều tra khi có khiếu nại về số dư.
- **Tiêu chí nghiệm thu:**
  1. **AC1 — Bảng truy vết toàn bộ giao dịch ví:** Hiển thị ai thực hiện (Admin, Operator hay Hệ thống), thời điểm, số tiền (màu sắc phân biệt credit/debit), loại giao dịch, số dư sau giao dịch, và lý do/ghi chú.
  2. **AC2 — Bộ lọc đa chiều:** Hỗ trợ lọc theo tài xế (tên/email), người thực hiện (admin/operator/hệ thống), loại giao dịch (`topup`, `charge`, `reservation_fee`, `no_show_fee`, `refund`, `manual_topup`, `adjustment`), và khoảng ngày (`date_from` - `date_to`).
  3. **AC3 — Chi tiết giao dịch & Metadata JSON:** Nút "Chi tiết" mở modal hiển thị đầy đủ các thông tin kỹ thuật và payload metadata JSON kèm tính năng sao chép 1-click.
  4. **AC4 — Thống kê tức thì:** 4 thẻ đo lường động (Tổng giao dịch, Tổng tiền nạp, Tổng tiền trừ, Số lượng tài khoản người thực hiện khác nhau).
  5. **AC5 — Xuất CSV:** Xuất toàn bộ dữ liệu theo bộ lọc hiện tại với định dạng UTF-8 BOM chuẩn tiếng Việt.
  6. **AC6 — Phân quyền chặt chẽ:** Chỉ các vai trò `admin`, `operator`, `accountant` mới được truy cập `/wallet/audit`.

### 1.2 Thành phần triển khai SCRUM-91
- **Template:** `frontend/templates/wallet/wallet_audit.html`
- **Styles:** `frontend/static/css/pages/wallet_audit.css`
- **Script:** `frontend/static/js/pages/wallet_audit.js`
- **API Client:** Bổ sung `ApiClient.listWalletAuditLogs(params)` trong `frontend/static/js/api_client.js`.
- **Backend Route:** Đăng ký `@router.get("/wallet/audit")` trong `backend/app/routers/pages.py`.
- **Navigation:** Bổ sung liên kết "Nhật ký ví" tại `frontend/templates/base.html`.

---

## PHẦN 2: SCRUM-92 — QUYỀN ĐƯỢC XÓA DỮ LIỆU CÁ NHÂN & LỊCH SỬ DI CHUYỂN (S-57)

### 2.1 Mục tiêu & Tiêu chí nghiệm thu (Acceptance Criteria)
- **User Story:** Là tài xế tôi muốn yêu cầu xoá thông tin cá nhân và lịch sử sạc của mình để thực hiện quyền theo Nghị định 13/2023/NĐ-CP (Bảo vệ dữ liệu cá nhân).
- **Tiêu chí nghiệm thu:**
  1. **AC1 — Yêu cầu xóa dữ liệu & Ẩn danh hóa lịch sử di chuyển:** Lịch sử sạc ghi nhận vị trí các trạm đã ghé là dữ liệu di chuyển nhạy cảm. Tài xế có form gửi yêu cầu ẩn danh hóa thông tin cá nhân (họ tên, email, SĐT, biển số xe) và tọa độ vị trí phiên sạc.
  2. **AC2 — Kiểm tra số dư ví (Balance Pre-check):** Nếu số dư ví `> 0 ₫`, hiển thị cảnh báo màu vàng bắt buộc phải rút hoặc hoàn tiền toàn bộ số dư trước khi yêu cầu được chấp thuận; nút gửi yêu cầu bị khóa để tránh vi phạm tài chính kế toán. Chỉ khi số dư `= 0 ₫` mới đủ điều kiện.
  3. **AC3 — Bảo toàn sổ cái và doanh thu kế toán:** Khi phê duyệt ẩn danh hóa, danh tính tài xế và tọa độ GPS của phiên sạc được băm/ẩn danh hóa một chiều; toàn bộ số liệu tổng hợp doanh thu và sổ cái giao dịch (`wallet_ledger`) được giữ nguyên tuân thủ Luật Kế toán.
  4. **AC4 — Tiến độ xử lý trực quan (Timeline):** Hiển thị trạng thái yêu cầu theo quy trình 3 bước: Tiếp nhận -> Thẩm định số dư/phiên sạc -> Thực hiện ẩn danh hóa.
  5. **AC5 — Quyền hủy yêu cầu:** Cho phép tài xế chủ động hủy yêu cầu khi đang ở trạng thái Chờ duyệt (`pending`).
  6. **AC6 — Giao diện quản trị viên (Admin/Operator/DPO):** Xem danh sách các yêu cầu xóa dữ liệu, kiểm tra tính hợp lệ (số dư = 0 ₫, không có phiên đang sạc), nút "Duyệt ẩn danh hóa" và nút "Từ chối" kèm lý do.

### 2.2 Thành phần triển khai SCRUM-92
- **Template:** `frontend/templates/privacy/privacy.html`
- **Styles:** `frontend/static/css/pages/privacy.css`
- **Script:** `frontend/static/js/pages/privacy.js`
- **API Client:** Bổ sung các hàm trong `frontend/static/js/api_client.js`:
  - `getPrivacyProfile()`
  - `requestDataDeletion(body)`
  - `cancelDataDeletionRequest(id)`
  - `listDataDeletionRequests(params)`
  - `approveDataDeletionRequest(id, body)`
  - `rejectDataDeletionRequest(id, body)`
- **Backend Route:** Đăng ký `@router.get("/privacy")` trong `backend/app/routers/pages.py`.
- **Navigation:** Bổ sung mục "Quyền riêng tư & Xóa DL" cho Driver và "Xóa dữ liệu (NĐ 13)" cho Admin/Operator tại `frontend/templates/base.html`.

---

## 3. Ma trận kiểm thử nghiệm thu (Test Matrix)

| Mã kiểm thử | Task | Kịch bản kiểm thử | Kết quả kỳ vọng | Trạng thái |
|:---:|:---:|---|---|:---:|
| **TC-91-01** | SCRUM-91 | Truy cập `/wallet/audit` với quyền admin/operator | Bảng tải dữ liệu giao dịch, hiển thị rõ ai thực hiện, số tiền, loại và số dư | **PASS** |
| **TC-91-02** | SCRUM-91 | Lọc theo loại giao dịch (topup, charge, manual_topup...) | Bảng cập nhật tức thì, hiển thị đúng các bản ghi thuộc loại đã chọn | **PASS** |
| **TC-91-03** | SCRUM-91 | Bấm nút "Chi tiết" tại một dòng giao dịch | Modal mở lên hiển thị đúng thông tin và metadata JSON có thụt dòng | **PASS** |
| **TC-91-04** | SCRUM-91 | Bấm nút "Xuất CSV" | File `wallet_audit_YYYY-MM-DD.csv` tải về có BOM UTF-8 không lỗi tiếng Việt | **PASS** |
| **TC-92-01** | SCRUM-92 | Truy cập `/privacy` với tài khoản tài xế có số dư > 0 ₫ | Cảnh báo màu vàng hiện lên, yêu cầu hoàn tiền trước, nút nộp yêu cầu bị khóa | **PASS** |
| **TC-92-02** | SCRUM-92 | Truy cập `/privacy` với tài khoản tài xế có số dư = 0 ₫ | Trạng thái hợp lệ hiện lên (xanh lá), form nộp yêu cầu sẵn sàng | **PASS** |
| **TC-92-03** | SCRUM-92 | Tài xế điền lý do, mật khẩu xác nhận, cam kết và gửi | Yêu cầu được gửi, chuyển sang thẻ tiến độ Timeline trạng thái "Đang xử lý" | **PASS** |
| **TC-92-04** | SCRUM-92 | Tài xế bấm "Hủy yêu cầu xóa dữ liệu" khi đang pending | Modal xác nhận, sau khi xác nhận form gửi yêu cầu quay trở lại ban đầu | **PASS** |
| **TC-92-05** | SCRUM-92 | Admin chuyển sang tab "Quản trị phê duyệt" | Xem danh sách các yêu cầu của tài xế kèm số dư ví và số phiên đang sạc | **PASS** |
| **TC-92-06** | SCRUM-92 | Admin duyệt yêu cầu tài xế có số dư ví = 0 ₫ | Modal cảnh báo xác nhận, chuyển trạng thái sang "Đã ẩn danh hóa" | **PASS** |
| **TC-92-07** | SCRUM-92 | Admin bấm nút "Duyệt" tài xế còn số dư > 0 ₫ | Nút duyệt bị vô hiệu hóa với tooltip cảnh báo phải hoàn tiền trước | **PASS** |
| **TC-92-08** | SCRUM-92 | Admin từ chối yêu cầu và nhập lý do | Modal nhập lý do, cập nhật trạng thái "Bị từ chối" và lưu lý do từ chối | **PASS** |
