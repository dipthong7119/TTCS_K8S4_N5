# Yêu cầu thực thi Task T-02: Cấu hình CI Pipeline

**AI Role**: DevOps & QA Engineer

## Ngữ cảnh (Context)
Dự án cần một Pipeline Continuous Integration (CI) tự động bằng GitHub Actions để đảm bảo chất lượng mã nguồn (Build, Lint, Test) mỗi khi có push hoặc pull request.
Hệ thống Backend sử dụng Python 3.11, framework FastAPI, công cụ Test `pytest` và công cụ Lint `ruff`.

## Nhiệm vụ (Tasks)

1. **Khởi tạo thư mục Test (`hardware/app/tests/`)**:
   - Tạo cấu trúc thư mục test: `hardware/app/tests/unit/`.
   - Tạo các file `__init__.py` để định dạng module Python.
   - Tạo test file `hardware/app/tests/unit/test_placeholder.py` có chứa 1 test case cơ bản (ví dụ assert True) làm điểm tựa cho các Unit Test sau.

2. **Cấu hình GitHub Actions (`.github/workflows/ci.yml`)**:
   - Tạo workflow tự động kích hoạt khi có sự kiện `push` hoặc `pull_request` vào nhánh chính.
   - Khai báo job chạy trên Ubuntu (`ubuntu-latest`).
   - Cấu hình các bước: Checkout code -> Cài đặt Python 3.11 -> Cài dependencies -> Chạy Linter (`ruff check .`) -> Chạy Test (`pytest`).
   - *Lưu ý*: Vì backend nằm trong thư mục `hardware/`, các bước chạy lệnh linter và test phải lấy `working-directory` là `hardware`.

3. **Bổ sung thư viện cần thiết (`hardware/requirements.txt`)**:
   - Chuyển `requirements.txt` từ thư mục gốc vào `hardware/requirements.txt` để tương thích với build context của Docker.
   - Đảm bảo trong `requirements.txt` có cài đặt `pytest`, `httpx` (để test API) và `ruff` (để lint).

## Tiêu chí Hoàn thành (AC)
- Khởi tạo chính xác file pipeline `.github/workflows/ci.yml`.
- Có file test mẫu để CI có thể thực thi và báo xanh.
- Đã sửa lại vị trí `requirements.txt` cho chuẩn chỉnh.
