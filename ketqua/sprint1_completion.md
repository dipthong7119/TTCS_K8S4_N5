# Báo cáo rà soát Sprint 1 — CSMS

## Nguồn đối chiếu

- Workbook gốc ở thư mục dự án, sheet `Backlog` và `Tasks`.
- `prompts/00_QUY_TAC_AGENT.md`, `prompts/01_CODEBASE_MAP.md`, `prompts/02_DAC_TA_DU_AN.md`, `prompts/SPRINT_1.md`.
- Năm vai trò hiện có: `driver`, `station_owner`, `operator`, `accountant`, `admin`.

## Đã kiểm tra/hoàn thiện cục bộ

- **S-02 / T-04–T-05:** năm vai trò và tài khoản demo; đăng nhập, cookie HttpOnly, khóa tạm theo tài khoản/IP và trang đích theo vai trò.
- **S-03 / T-06–T-07:** route API mặc định từ chối nếu chưa khai quyền; truy vấn/lưới theo dõi giới hạn theo quyền chủ sở hữu.
- **S-04 / T-08–T-09:** CRUD trạm, validation và phân quyền. Trạm mới dùng `active` theo schema T-08, theo lựa chọn của người dùng.
- **S-05 / T-10–T-11:** mã trụ unique ở cơ sở dữ liệu, API kiểm tra mã trùng và ô nhập kiểm tra khi rời trường; test tạo/sửa/xóa lặp 10 vòng. Đầu nối mới dùng `unavailable` theo schema T-10. Migration mới `d4e9f7210b8c` sửa mặc định schema hiện hành mà không sửa migration lịch sử hoặc đổi trạng thái các đầu nối đã tồn tại.
- **Khóa trạm:** `inactive` là tạm ngừng, trụ vẫn Boot/kết nối để báo trạng thái; `locked` là trạng thái riêng chỉ admin được đặt/mở, Boot của trụ thuộc trạm khóa trả `Rejected`.
- **K-01:** tài liệu trace và JSONL mẫu đã có trong `ketqua/`; phần trace trước đó dùng simulator/môi trường mock, không đại diện cho kiểm thử staging.

## Còn mở theo tiêu chí Excel

- **S-01 / T-01–T-03:** người dùng đã gửi ảnh cho thấy cả ba GitHub checks xanh tại thời điểm ảnh được chụp. Trong lượt rà soát cục bộ này `docker compose config` hợp lệ, nhưng Docker Engine không khả dụng nên không chạy được container hoặc kiểm tra deploy/rollback staging. Vì chưa có bằng chứng cho toàn bộ tiêu chí chạy thật/rollback, S-01 và T-01–T-03 vẫn `In Progress`.
- **S-05:** các chức năng khai báo trụ và đầu nối đã được kiểm tra; điều kiện “đã có phiên sạc thì từ chối sửa mã trụ kèm lý do” chưa thể kiểm chứng đầy đủ vì mô hình phiên sạc thuộc sprint sau. S-05 vẫn `In Progress`.

## Bằng chứng test mới nhất

- Toàn bộ suite chạy 10 lần liên tiếp: mỗi lần **101 passed**, không có test thất bại.
- Trong mỗi lượt, test CRUD lặp 10 trạm và 10 trụ; tổng cộng 100 vòng cho từng loại qua 10 lượt.
- `run.ps1` đã chạy migration mới và khởi động ứng dụng; `/health` và `/login` trả HTTP 200. Docker Compose chỉ kiểm tra cấu hình được vì thiếu Docker Engine.

Bản workbook đã đối chiếu được lưu riêng thành `outputs/sprint2-2026-09-27/CSMS_sprint1_sprint2_review.xlsx`; file gốc không bị ghi đè.

## Cập nhật hiện trạng 2026-09-27

- Compose hiện định nghĩa PostgreSQL 15, volume riêng, healthcheck DB và chạy migration trước khi mở HTTP; cấu hình đạt. CI chạy trên mọi push và pull request.
- Docker Engine không khả dụng nên chưa chạy container, PostgreSQL, GitHub Actions sau thay đổi, staging deploy hoặc rollback. S-01 và T-01–T-03 vẫn In Progress.
- Lần chạy suite mới nhất sau bổ sung kiểm thử đạt 87 passed. S-05 vẫn mở vì tiêu chí khóa sửa mã trụ khi đã có phiên sạc phụ thuộc bảng phiên sạc của Sprint 3.
