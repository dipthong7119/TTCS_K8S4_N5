# Kiểm thử Sprint 2 và cách khởi động

## Kiểm thử

- Chạy toàn bộ suite **10 lần liên tiếp**: cả 10 lượt đều **101 passed**, 0 failed (tổng cộng 1.010 lượt test).
- Bài CRUD trong suite chạy 10 vòng tạo/đọc/sửa/xóa trạm và 10 vòng tạo/đọc/sửa/xóa trụ mỗi lượt. Qua 10 lần chạy suite tương đương **100 vòng CRUD trạm và 100 vòng CRUD trụ**; thao tác mã trụ trùng và trạng thái đầu nối cũng được kiểm tra.
- `ruff check backend/app backend/alembic tests`: đạt.
- JavaScript đã qua `node --check`; `run.ps1` qua kiểm tra cú pháp PowerShell; `docker compose config --quiet` đạt.
- Test migration xác nhận nâng/hạ schema, đủ năm vai trò, mã email/mã thẻ duy nhất và đầu nối mới mặc định `unavailable`.

## Chạy ứng dụng

- `.\run.ps1` đã chạy được, áp dụng migration `d4e9f7210b8c`, khởi động Uvicorn; `/health` và `/login` đều trả HTTP 200.
- Khi gửi Ctrl+C, server hoàn tất shutdown và in `CSMS đã dừng theo yêu cầu.`; không còn traceback `KeyboardInterrupt` trong log. PTY kiểm thử trả mã phiên 1 sau tín hiệu Ctrl+C dù server đã đóng gọn.
- File `docker-compose.yml` hợp lệ và dùng SQLite ở `backend/csms.db`, cùng file với `run.ps1`. Máy hiện tại không có Docker Engine/daemon khả dụng nên chưa chạy được `docker compose up`, simulator trong container hoặc staging deployment.

Mỗi lượt test có 8 cảnh báo từ phiên bản thư viện/config Alembic, không làm test thất bại. Xem `sprint1_completion.md` để biết các tiêu chí còn mở ở Sprint 1.

## Cập nhật hiện trạng 2026-09-27

- Lần chạy toàn suite mới nhất đạt 87 passed, 0 failed; Ruff đạt; 9 file JavaScript qua kiểm tra cú pháp.
- Compose hiện dùng PostgreSQL 15 với volume riêng; run.ps1 vẫn dùng SQLite. Cấu hình Compose đạt, nhưng Docker Engine không khả dụng nên chưa chạy được container hoặc staging deployment.
