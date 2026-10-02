# Phân công công việc Sprint 1

Dựa trên danh sách thành viên trong `infomember.md`, các task trong `SPRINT_1.md` và mã Jira trên hình `anh sprint1.png`, dưới đây là bảng phân công chi tiết đã được ánh xạ với mã SCRUM:

## 1. Nhóm Developer Backend

**Thành viên:** Ngô Quang Tùng, Nguyễn Lâm Tùng, Hoàng Văn Tân

| Thành viên | Mã Jira (Task) | Mô tả công việc |
| :--- | :--- | :--- |
| **Ngô Quang Tùng (NT)** | SCRUM-99 (T-01),<br>SCRUM-100 (T-02),<br>SCRUM-101 (T-03) | Xây dựng khung dự án (FastAPI, config, database, Docker), cấu hình CI/CD Pipeline (GitHub Actions) và deploy tự động lên staging. |
| **Nguyễn Lâm Tùng (NT)** | **SCRUM-12 (T-04)**,<br>SCRUM-102 (T-06),<br>SCRUM-103 (T-07),<br>K-01 (Spike) | Xây dựng DB users/roles, viết Middleware kiểm tra quyền truy cập (require_role), API lọc quyền sở hữu, và viết Spike Simulator cho trụ sạc (WebSocket/OCPP). *(Lưu ý: SCRUM-12 đang được gán cho NT trên Jira)* |
| **Hoàng Văn Tân** | SCRUM-104 (T-08),<br>SCRUM-106 (T-10),<br>Hỗ trợ API cho SCRUM-13, 105, 107 | Thiết kế DB cho trạm (stations), trụ sạc & đầu nối (charge_points, connectors). Xây dựng Backend API cho các tính năng: Đăng nhập, CRUD Trạm, và Thêm trụ. |

## 2. Nhóm Developer Frontend

**Thành viên:** Phạm Văn Tuấn, Vy Hoàng Tú, Đặng Ngoc Đại

| Thành viên | Mã Jira (Task) | Mô tả công việc |
| :--- | :--- | :--- |
| **Phạm Văn Tuấn (PT)** | **SCRUM-13 (T-05)** | Xây dựng màn hình đăng nhập (`login.html`), xử lý hiển thị thông báo lỗi khi sai thông tin và trạng thái khóa tạm. Phối hợp với Backend (Tân) để ghép API. *(Lưu ý: SCRUM-13 đang được gán cho PT trên Jira)* |
| **Vy Hoàng Tú** | SCRUM-105 (T-09) | Xây dựng giao diện danh sách trạm, form tạo/sửa trạm (`list.html`, `form.html`). Kết nối API lấy danh sách. |
| **Đặng Ngoc Đại** | SCRUM-107 (T-11) | Xây dựng form thêm trụ, đầu nối vào chi tiết trạm. Thêm logic gọi API kiểm tra mã trùng lặp ngay khi vừa nhập liệu xong. |

## 3. Nhóm Tester

**Thành viên:** Tạ Như Vinh, Hoàng Văn Đức

| Thành viên | Mã Jira (Task) | Mô tả công việc |
| :--- | :--- | :--- |
| **Tạ Như Vinh** | Backend QA, Security,<br>K-01 | Viết unit test cho Backend, kiểm thử bảo mật Middleware (gọi sai quyền SCRUM-102, 103), chạy giả lập K-01 kiểm tra hoạt động. |
| **Hoàng Văn Đức** | Frontend QA, Luồng UI,<br>CI/CD | Kiểm thử E2E trên màn hình (đăng nhập, tạo trạm, thêm trụ), test lỗi hiển thị UI (SCRUM-13, 105, 107), xác nhận CI/CD chạy thành công. |

---

**Ghi chú:**
- Các mã `SCRUM-XXX` đã được đồng bộ với Board Jira. Task `K-01` hiện chưa có trên Jira, cần tạo bổ sung.
- Các bạn Developer nên tham khảo kỹ các ràng buộc kỹ thuật (NFR) và tiêu chí hoàn thành (AC) trong file `SPRINT_1.md`.
- Các công việc cần có sự kết nối giữa Frontend và Backend (SCRUM-13, 105, 107) thì hai bên cần phối hợp làm chuẩn các request/response schema.
- Tester chú ý check list **Definition of Done (Sprint 1)** trước khi báo cáo hoàn thành cho từng hạng mục.
