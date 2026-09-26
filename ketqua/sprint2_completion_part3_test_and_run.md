**Kết quả kiểm thử trên Web và tạo Script khởi chạy Local**

1. **Kiểm thử đăng nhập và giao diện Web (Docker)**
Tôi đã viết script tự động truy cập vào HTTP server ở `http://localhost:8000/`:
- **Chuyển hướng tự động (Redirect):** Khi vào trang gốc `/`, hệ thống tự động đẩy về `/login` thành công (HTTP 200).
- **Đăng nhập API:** Gửi form JSON đến `/api/auth/login` với tài khoản `admin@csms.local`. Đăng nhập thành công, nhận JWT session cookie và thông tin vai trò `["admin"]`.
- **Giao diện theo dõi:** Vào `/monitoring` thành công (HTTP 200), giao diện giám sát dạng lưới được nạp lên đúng cách. Gọi `/api/monitoring/tree` trả về đầy đủ mảng JSON danh sách trạm.
-> Hệ thống qua Docker hoạt động hoàn toàn mượt mà.

2. **Tạo Script `run.ps1` (Khởi chạy bằng PowerShell)**
- Để tiện cho bạn không cần phụ thuộc vào Docker Desktop, tôi đã tạo file `run.ps1` ở thư mục gốc của dự án.
- Khi bạn nháy đúp hoặc gõ `.\run.ps1` vào terminal, nó sẽ:
  - Tự động phát hiện và cài đặt môi trường ảo `.venv` nếu chưa có.
  - Tự động cập nhật `requirements.txt`.
  - Tự động sao chép `.env.example` thành `.env` (nếu bạn chưa có).
  - Tự động chạy `alembic upgrade head` để đảm bảo cấu trúc database luôn mới nhất.
  - Tự động gọi `uvicorn` (thông qua `run.py`) để chạy server.

Giờ đây bạn có thể mở terminal và gõ `.\run.ps1` là code chạy thẳng trên máy tính luôn!
