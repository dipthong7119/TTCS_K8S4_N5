# Kết quả thực hiện SCRUM-184 — Xuất bảng đối chiếu kết quả kWh

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)  
**Vai trò:** Frontend Developer (Sprint 3)  
**Task cha:** T-46 (Kịch bản 20 trụ ảo ngắt–nối ngẫu nhiên, kiểm kWh cuối)  
**Story tham chiếu:** S-21 (Phiên đang dở được khôi phục đúng khi trụ nối lại) & Epic E-04  
**SP:** 1  
**Reviewer:** Vy Hoàng Tú  
**Trạng thái:** Hoàn tất 100% triển khai Frontend & Tích hợp API  

---

### 1. Mục tiêu và Tiêu chí nghiệm thu (Acceptance Criteria)

- **Mục tiêu:** Cung cấp giao diện trực quan cho quản trị viên và vận hành viên đối chiếu số liệu điện năng (kWh) giữa hệ thống CSMS và thiết bị mô phỏng (OCPP Simulator), phát hiện sai lệch khi trụ sạc bị ngắt - nối ngẫu nhiên và hỗ trợ trích xuất báo cáo nghiệm thu cho S-21 / E-04.
- **Tiêu chí nghiệm thu:**
  1. Màn hình chuyên dụng tại route `/sessions/kwh-reconciliation`, phân quyền chỉ cho `admin` và `operator`.
  2. Kết nối API authoritative `GET /api/reconciliation/kwh` thông qua module trung tâm `ApiClient.getKwhReconciliation()`.
  3. Cơ chế fallback an toàn: khi chưa có dữ liệu chạy kịch bản thật từ SCRUM-182, tự động tải dữ liệu mẫu chuẩn và hiển thị thông báo `#recon-mock-notice`.
  4. Hiển thị bảng đối chiếu 11 cột rõ ràng, trực quan, phân biệt rõ các ca Khớp (`MATCH`), Lệch (`MISMATCH`), Thiếu bên hệ thống (`MISSING_IN_SYSTEM`), Thiếu bên simulator (`MISSING_IN_SIMULATOR`).
  5. Hỗ trợ bộ lọc nhanh theo trạm sạc, lọc theo trạng thái kết quả, tìm kiếm từ khóa thời gian thực.
  6. Cho phép sắp xếp theo từng cột (Mã trụ, Đo đầu, Đo cuối, Ngắt nối, kWh, v.v.).
  7. Xuất báo cáo dữ liệu với 2 định dạng: **CSV (UTF-8 có BOM tương thích Excel)** và **Markdown (GitHub-flavored Markdown)**.

---

### 2. Các thành phần đã triển khai

| Thành phần | Đường dẫn file | Mô tả chi tiết |
|------------|----------------|----------------|
| **HTML Template** | `frontend/templates/sessions/kwh_reconciliation.html` | Kế thừa `base.html`, breadcrumb chuẩn SEO, header KPIs cards, banner Verdict, thanh công cụ tìm kiếm/lọc, nút xuất CSV/MD, bảng dữ liệu. |
| **Styles (CSS)** | `frontend/static/css/pages/kwh_reconciliation.css` | Giao diện hiện đại, responsive, badge trạng thái màu sắc tương phản, highlight dòng lệch điện năng, icon đếm số lần ngắt kết nối. |
| **Logic (JavaScript)** | `frontend/static/js/pages/kwh_reconciliation.js` | Quản lý state dữ liệu, gọi `ApiClient.getKwhReconciliation()`, đồng bộ danh sách trạm qua `ApiClient.getMonitoringTree()`, tìm kiếm, lọc, sắp xếp và thuật toán xuất file CSV/Markdown. |
| **API Client** | `frontend/static/js/api_client.js` | Bổ sung phương thức `getKwhReconciliation(params, opts)` chuẩn hóa toàn bộ lời gọi API qua module dùng chung. |
| **Router Backend** | `backend/app/routers/pages.py` | Đăng ký route giao diện `GET /sessions/kwh-reconciliation` với dependency kiểm tra quyền `require_role("admin", "operator")`. |
| **Menu Điều hướng** | `frontend/templates/base.html` | Bổ sung mục "Đối chiếu kWh" trong thanh menu bên trái (Sidebar) cho nhóm người dùng quản trị / vận hành. |

---

### 3. Ma trận kiểm thử nghiệm thu (Test Cases)

| Mã Test | Mô tả kịch bản kiểm thử | Kết quả kỳ vọng | Trạng thái |
|:---|:---|:---|:---:|
| **TC-184-01** | Truy cập route `/sessions/kwh-reconciliation` bằng tài khoản driver | Chặn truy cập hoặc chuyển hướng, chỉ role `admin`/`operator` truy cập được | **PASS** |
| **TC-184-02** | Gọi API qua `ApiClient.getKwhReconciliation()` | Lấy dữ liệu đối chiếu thành công từ `GET /api/reconciliation/kwh` | **PASS** |
| **TC-184-03** | Khả năng tự phục hồi fallback khi thiếu file kịch bản thật | Hệ thống hiển thị badge thông báo dữ liệu mẫu và nạp bảng mượt mà không vỡ giao diện | **PASS** |
| **TC-184-04** | Hiển thị Summary Cards & Verdict Banner | Hiển thị chính xác tổng phiên, số phiên khớp, sai lệch kWh, tỷ lệ % và verdict `PASSED` / `FAILED` | **PASS** |
| **TC-184-05** | Tìm kiếm từ khóa theo mã trụ hoặc tên trạm | Bảng lọc kết quả ngay lập tức khi người dùng nhập ký tự tìm kiếm | **PASS** |
| **TC-184-06** | Bộ lọc theo trạng thái (`Khớp`, `Lệch`, `Thiếu`) | Danh sách hiển thị đúng các hàng thỏa mãn trạng thái đã chọn | **PASS** |
| **TC-184-07** | Nhấp tiêu đề cột để sắp xếp dữ liệu (Sort) | Dữ liệu đảo chiều tăng dần / giảm dần kèm icon chỉ hướng `↑` / `↓` | **PASS** |
| **TC-184-08** | Bấm nút "Xuất CSV" | Tải xuống file `.csv` chứa ký tự tiếng Việt chuẩn (BOM UTF-8), mở tốt trong Excel | **PASS** |
| **TC-184-09** | Bấm nút "Xuất Markdown" | Tải xuống file `.md` chứa bảng định dạng chuẩn GitHub Markdown phục vụ báo cáo | **PASS** |

---

### 4. Kết luận & Chuyển giao

- Task **SCRUM-184 (1 SP)** đã hoàn thành toàn diện, đáp ứng 100% tiêu chí nghiệm thu.
- Đã liên kết và kiểm chứng tích hợp thành công với backend endpoint do Hoàng Văn Đức cung cấp (`GET /api/reconciliation/kwh`).
- Sẵn sàng bàn giao cho Reviewer (**Vy Hoàng Tú**) kiểm tra và làm tiền đề số liệu cho nhiệm vụ nghiệm thu cuối cùng **SCRUM-186** (Bằng chứng kiểm thử cho AC của S-21 và E-04).
