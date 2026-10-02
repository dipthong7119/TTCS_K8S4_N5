# Yêu cầu thực thi Backend QA Sprint 1

**Người thực hiện**: Tạ Như Vinh
**Vai trò**: Backend QA, Security Tester
**Branch**: TA-VINH
**Ngày**: 2026-09-25

## Tài liệu bắt buộc đọc trước

Trước khi viết test, phải đọc và đối chiếu đầy đủ các file:

1. `prompts/01_CODEBASE_MAP.md`
2. `prompts/02_CODING_STANDARDS.md`
3. `prompts/03_SSD_SPEC.md`
4. `prompts/SPRINT_1.md`
5. `prompts/plant-sprint1.md`

Phải kiểm tra source hiện tại trong `backend/`, không tự suy diễn endpoint hoặc
chức năng chưa tồn tại. Theo quy trình bàn giao của trưởng nhóm, toàn bộ artifact
QA trong yêu cầu này đặt tại thư mục `tests/` ở root, ngang hàng với `backend/`
và `frontend/`. Không sửa code của developer.

## Nhiệm vụ

1. Tạo fixture pytest dùng SQLite riêng, không đọc/ghi `backend/csms.db`.
2. Override FastAPI dependency `get_db` để API test dùng database test.
3. Kiểm thử T-04 / SCRUM-12:
   - Alembic migration chạy tiến đến `head` và chạy lùi về `base`.
   - Seed có đúng 5 role: driver, station_owner, operator, accountant, admin.
   - `users.email` có ràng buộc unique.
   - Tài khoản demo seed phải xác thực được bằng mật khẩu công bố trong README.
4. Kiểm thử T-05 / SCRUM-13 và SSD-1:
   - Sai email và sai mật khẩu trả cùng một lỗi chung.
   - Lần sai thứ 6 bị khóa 15 phút.
   - Nhập đúng mật khẩu trong lúc khóa vẫn bị từ chối.
   - Trạng thái khóa còn sau khi tạo lại TestClient.
   - Đăng nhập thành công tạo cookie HttpOnly và reset bộ đếm sai.
   - Bảo vệ đăng nhập sai theo tài khoản và theo IP.
5. Kiểm thử endpoint `/health` theo contract test hiện có.
6. Chạy toàn bộ test, không sửa assertion để chiều theo code đang lỗi.
7. Ghi kết quả pass/fail và blocker vào file báo cáo trong `tests/`.

## Ràng buộc

- Dùng `pytest`, FastAPI `TestClient`, SQLAlchemy và Alembic đã có trong dự án.
- Không thêm package trùng chức năng.
- Không hardcode secret và không log mật khẩu/token.
- Mỗi file test chỉ kiểm thử một nhóm hành vi.
- SCRUM-102, SCRUM-103 và K-01 chỉ viết test khi source tương ứng đã có trên
  `main`; nếu chưa có thì ghi rõ là blocked, không giả lập code developer.
- Test fail do sản phẩm là kết quả QA hợp lệ và phải được ghi vào báo cáo.

## Đầu ra yêu cầu

```text
tests/
|-- backend_qa_prompt.md
|-- backend_qa_prompt_ket_qua.md
|-- backend_test_results.md
|-- conftest.py
|-- test_auth.py
|-- test_health.py
`-- test_migrations.py
```

## Tiêu chí hoàn thành

- Test không làm thay đổi database thật.
- Test code vượt qua `ruff check tests`.
- Có output pytest thực tế trong file báo cáo.
- Mỗi test fail có kết quả mong đợi, kết quả thực tế và vị trí source liên quan.
- Không sửa file ngoài thư mục root `tests/`.
