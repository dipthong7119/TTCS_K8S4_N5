# Kết quả kiểm thử SCRUM-135 — Kiểm thử Đăng nhập, Khóa IP & Tài khoản sau 5 lần sai, Route Guard

**Người thực hiện:** Hoàng Văn Đức (Tester Sprint 2)  
**Ngày thực hiện:** 2026-10-04  
**Trạng thái:** ✅ Completed (10/10 test cases PASS)  
**Môi trường:** Docker Compose (`csms_app`, `csms_db`)

---

## 1. Tóm tắt kết quả kiểm thử

| Mã TC | Tên ca kiểm thử | Mức độ | Kết quả | Ghi chú thực tế |
| :--- | :--- | :---: | :---: | :--- |
| **TC-135-01** | Đăng nhập thành công, redirect đúng role | P0 | ✅ PASS | Đăng nhập thành công 5 vai trò; session cookie HttpOnly được set; redirect đúng trang chủ (`admin`/`operator` -> `/monitoring`, `driver` -> `/sessions/mine`, `station_owner` -> `/stations`, `accountant` -> `/wallet`). |
| **TC-135-02** | Sai mật khẩu → thông báo lỗi chung | P0 | ✅ PASS | Nhận HTTP 401 với thông báo bảo mật chung: `"email hoặc mật khẩu không đúng"`. |
| **TC-135-03** | Email không tồn tại → cùng thông báo lỗi | P0 | ✅ PASS | Nhận HTTP 401 với thông báo giống hệt TC-135-02, hoàn toàn không tiết lộ email có tồn tại hay không. |
| **TC-135-04** | Khóa tài khoản sau 5 lần sai liên tiếp | P0 | ✅ PASS | Sau 5 lần nhập sai: `user.failed_login_count = 5`, `user.locked_until = NOW + 15 phút`; lần 6 nhập đúng mật khẩu vẫn bị từ chối với HTTP 401: `"tài khoản tạm khoá 15 phút"`. |
| **TC-135-05** | Khóa theo IP sau 5 lần sai từ cùng IP | P0 | ✅ PASS | Nhập sai 5 lần từ cùng IP (dù dùng email giả): bảng `login_ip_attempts` ghi nhận `failed_login_count >= 5` và `locked_until = NOW + 15 phút`; lần 6 từ IP đó bị chặn với HTTP 401: `"tài khoản tạm khoá 15 phút"`. |
| **TC-135-06** | Khóa tự mở sau 15 phút | P1 | ✅ PASS | Khi `locked_until` đã qua, đăng nhập lại thành công với mật khẩu đúng; `failed_login_count` tự động reset về 0, `locked_until = NULL`. |
| **TC-135-07** | Đăng nhập thành công reset bộ đếm sai | P1 | ✅ PASS | Sai 3 lần -> đăng nhập đúng ở lần 4 -> counter reset về 0; khi nhập sai lần tiếp theo bộ đếm bắt đầu lại từ 1 (không cộng dồn lên 4). |
| **TC-135-08** | Route guard chặn trang cần auth | P0 | ✅ PASS | Truy cập endpoint nội bộ (`/api/monitoring/tree`) khi không có session cookie xác thực bị chặn ngay với HTTP 401. |
| **TC-135-09** | Nút hiện/ẩn mật khẩu (password toggle) | P2 | ✅ PASS | Template `login.html` có nút `#password-toggle` với icon mắt SVG, chuyển đổi mượt mà giữa `type="password"` và `type="text"`, cập nhật thuộc tính accessibility `aria-pressed`. |
| **TC-135-10** | Form không submit khi email/password trống | P1 | ✅ PASS | Template `login.html` khai báo thuộc tính `required` cho cả email và password, tích hợp `FormGuard.protect` ngăn chặn submit rỗng từ client. |

---

## 2. Kịch bản kiểm chứng tự động
- Script kịch bản kiểm thử: [`tests/test_scrum135_live.py`](file:///d:/TTCS_K8S4_N5/tests/test_scrum135_live.py)
- Kết quả chạy trên môi trường Docker PostgreSQL: **10/10 test cases đạt PASS**.
- Linter Ruff: **All checks passed**.

---

## 3. Kết luận nghiệm thu
Task **SCRUM-135** đã hoàn thành xuất sắc toàn bộ Acceptance Criteria:
1. Cơ chế phòng thủ Brute Force hai lớp (theo tài khoản và theo địa chỉ IP) hoạt động chuẩn xác, lưu bền vững trong cơ sở dữ liệu PostgreSQL.
2. Thông báo lỗi đăng nhập tuân thủ nguyên tắc an toàn thông tin OWASP (không tiết lộ sự tồn tại của tài khoản).
3. Cơ chế phân quyền và bảo vệ route qua session cookie HttpOnly hoạt động bảo mật.
