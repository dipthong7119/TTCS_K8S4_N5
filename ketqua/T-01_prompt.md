# Yêu cầu thực thi Task T-01: Khởi tạo khung dự án

**AI Role**: Developer Backend & DevOps

## Ngữ cảnh (Context)
Dự án **Nền tảng vận hành trạm sạc xe điện (CSMS)** được xây dựng bằng Python (FastAPI), Cơ sở dữ liệu SQLite, và chạy trên nền tảng Docker. Kiến trúc hệ thống dựa vào tài liệu `01_CODEBASE_MAP.md` và `SPRINT_1.md`.

## Nhiệm vụ (Tasks)
Vui lòng thực hiện chuẩn xác các yêu cầu kỹ thuật sau:

1. **Khởi tạo Ứng dụng FastAPI (`hardware/app/main.py`)**:
   - Tạo instance `FastAPI` (title="CSMS", version="1.0.0").
   - Viết API `/health` trả về chuẩn JSON `{"status": "ok"}` nhằm phục vụ hệ thống Docker/Load Balancer kiểm tra sức khoẻ ứng dụng (healthcheck).

2. **Đóng gói Docker (`hardware/Dockerfile` & `docker-compose.yml`)**:
   - **Dockerfile**: Base image `python:3.11-slim`, copy mã nguồn, thiết lập biến môi trường khắc phục lỗi buffer log (`PYTHONUNBUFFERED=1`), cài đặt thư viện từ `requirements.txt` và khởi chạy server bằng `uvicorn` trên port 8000.
   - **docker-compose.yml**: Khai báo service `app` build từ `hardware/Dockerfile`, map cổng 8000. Lưu ý quan trọng: Map volume file CSDL `csms.db` từ môi trường host vào trong container để dữ liệu SQLite không bị mất khi container bị xoá. Thiết lập `healthcheck` thông qua lệnh curl gọi vào API `/health`.

3. **Cấu hình Database Migration (Alembic)**:
   - Khởi tạo thư mục migration tại `hardware/alembic`.
   - Cấu hình file `hardware/alembic.ini` và `hardware/alembic/env.py`. Trong `env.py`, import và thiết lập `target_metadata` trỏ tới `app.database.Base` để Alembic có thể tự động đọc và tạo file migration theo Models (`autogenerate`).

4. **Cấu hình Testing (`hardware/pytest.ini`)**:
   - Thêm file cấu hình pytest với cờ `asyncio_mode = auto` để sẵn sàng cho quy trình Unit Test.

5. **Cập nhật tài liệu (`README.md`)**:
   - Mô tả hướng dẫn cụ thể cách setup môi trường, cách sử dụng lệnh Docker, cách tạo và migrate Database bằng lệnh Alembic, quy định quản lý mã nguồn, và quy định lưu các file prompt/log trong thư mục `promtp/`.

## Tiêu chí Hoàn thành (Acceptance Criteria - AC)
- Khởi chạy thành công dự án thông qua lệnh `docker-compose up -d --build`.
- Endpoint `http://localhost:8000/health` trả về kết quả 200 OK.
- Cấu trúc thư mục được sắp xếp chuẩn theo thiết kế, không có hardcode thông tin kết nối DB.
