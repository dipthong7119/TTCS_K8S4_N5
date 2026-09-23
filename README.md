# Nền tảng vận hành trạm sạc xe điện (CSMS)

Dự án phát triển phần mềm quản lý trạm sạc xe điện sử dụng FastAPI (Backend) và HTML/CSS/JS (Frontend).
Mô phỏng trụ sạc bằng thư viện Python. Database hiện tại sử dụng **SQLite**.

## Cấu trúc thư mục 
- `hardware/`: Mã nguồn Backend (Python/FastAPI)
- `giaodien/`: Mã nguồn Frontend (HTML/CSS/JS)
- `promtp/`: Thư mục lưu trữ log/prompt theo yêu cầu riêng biệt của team.

## Hướng dẫn cho Quản lý Mã nguồn & Developer

### 1. Yêu cầu môi trường
- Python 3.11+
- Docker & Docker Compose
- Khuyến nghị bắt buộc tạo môi trường ảo (Virtual Environment) khi lập trình tại local.

### 2. Khởi chạy nhanh bằng Docker
```bash
# Clone repository
git clone <url_repo>
cd TTCS_K8S4_N5

# Chép file cấu hình mẫu (Tạo file .env)
cp .env.example .env

# Chạy hệ thống bằng Docker Compose (Khởi tạo App & map SQLite local)
docker-compose up -d --build
```
Hệ thống sẽ chạy tại `http://localhost:8000`. Bạn có thể kiểm tra Health Check tại `http://localhost:8000/health`.

### 3. Quy trình làm việc với Database (Alembic)
Mọi thay đổi liên quan đến cấu trúc Cơ sở dữ liệu (tạo bảng, thêm cột) phải thông qua **Alembic**:
1. Định nghĩa Models trong `hardware/app/models/`
2. Tạo file migration:
```bash
cd hardware
alembic revision --autogenerate -m "thêm_bảng_users"
```
3. Cập nhật DB:
```bash
alembic upgrade head
```

### 4. Cấu hình CI/CD & Deploy tự động (Staging)
Dự án được cấu hình Pipeline (Build, Test, Deploy) qua **GitHub Actions**. Để luồng Deploy (`deploy.yml`) hoạt động, Developer/Admin cần vào tab **Settings > Secrets and variables > Actions** trên GitHub và thiết lập các biến sau:
- `STAGING_HOST`: Địa chỉ IP hoặc Domain của server Staging.
- `STAGING_USERNAME`: Tên người dùng SSH (ví dụ: `ubuntu`).
- `STAGING_SSH_KEY`: Private Key SSH dùng để kết nối vào máy chủ.
- `STAGING_SSH_PORT`: Cổng kết nối (thường là `22`).
- `GHCR_PAT`: Personal Access Token của GitHub có quyền pull package từ GHCR.

### 5. Quy tắc Commit & Quản lý
- Các Task được giao theo Sprint cần được làm từng phần.
- Sau khi hoàn thành một chức năng, phải ghi lại log/prompt tại thư mục `promtp/` kèm theo kết quả `_ket_qua` tương ứng.
- **Không commit** file chứa dữ liệu nhạy cảm (như `.env`, `.sqlite` / `csms.db`).
