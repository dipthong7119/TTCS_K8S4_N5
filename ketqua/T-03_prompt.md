# Yêu cầu thực thi Task T-03: Triển khai tự động lên Staging

**AI Role**: DevOps Engineer

## Ngữ cảnh (Context)
Dự án cần tự động hóa quá trình Deploy ứng dụng lên máy chủ Staging mỗi khi nhánh `main` được cập nhật. Yêu cầu là đóng gói ứng dụng thành Docker Image, đẩy lên kho chứa (Registry) và triển khai từ xa. Quan trọng nhất là cần bước kiểm tra sức khoẻ (Health check); nếu triển khai hỏng thì không làm ảnh hưởng phiên bản cũ.

## Nhiệm vụ (Tasks)

1. **Cấu hình Pipeline CD (`.github/workflows/deploy.yml`)**:
   - Tạo file workflow kích hoạt khi có Push vào nhánh `main`.
   - **Các bước thực hiện trong Pipeline**:
     - Checkout mã nguồn.
     - Đăng nhập vào GitHub Container Registry (GHCR) sử dụng `GITHUB_TOKEN`.
     - Build Docker image từ thư mục `hardware/` và đẩy image (push) lên GHCR.
     - Sử dụng thư viện truy cập SSH (như `appleboy/ssh-action`) kết nối vào máy chủ Staging để:
       - Pull Docker image mới nhất.
       - Khởi động lại container bằng `docker-compose up -d`.
       - Thực hiện `curl` kiểm tra API `/health`. Nếu status không phải 200, báo lỗi pipeline để DevOps biết.

2. **Cập nhật tài liệu (`README.md`)**:
   - Bổ sung vào tài liệu hướng dẫn cách thiết lập các tham số bảo mật (Secrets) trên kho lưu trữ GitHub để action Deploy có thể kết nối thành công vào server.

## Tiêu chí Hoàn thành (AC)
- Khởi tạo chính xác file cấu hình `.github/workflows/deploy.yml`.
- Workflow có tích hợp bước kiểm tra healthcheck và log thông báo trạng thái.
- Đã ghi tài liệu dặn dò đầy đủ cách setup Secrets cho anh em DevOps.
