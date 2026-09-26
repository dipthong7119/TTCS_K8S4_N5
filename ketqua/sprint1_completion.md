# Báo cáo rà soát và hoàn thiện Sprint 1 — CSMS

## Tài liệu đối chiếu

- Workbook `Nền tảng vận hành trạm sạc xe điện (CSMS).xlsx`, hai sheet `Backlog` và `Tasks`.
- Các quy tắc trong `prompts/00_QUY_TAC_AGENT.md`, `prompts/01_CODEBASE_MAP.md`, `prompts/02_DAC_TA_DU_AN.md` và `prompts/SPRINT_1.md`.
- Năm vai trò seed có sẵn: driver, station_owner, operator, accountant và admin.

## Phần đã triển khai

- **T-04/T-05, S-02:** giữ năm vai trò; login dùng cookie HttpOnly, khóa theo tài khoản và IP sau ngưỡng cấu hình, trả lỗi chung; mỗi vai trò có trang đích riêng. Tham số `next` chỉ được dùng nếu cùng origin. Bộ đếm IP nằm ở bảng riêng để không tạo tài khoản giả trong `users`.
- **T-06/T-07, S-03:** giữ cơ chế mặc định từ chối route API thiếu quyền, lọc trạm theo chủ sở hữu, giới hạn trang web theo vai trò và chỉ gửi SSE trạng thái trạm tới đúng chủ trạm hoặc vai trò vận hành/quản trị.
- **T-08/T-09, S-04:** trạm mới ở trạng thái `active` theo lựa chọn đã xác nhận; CRUD 10 vòng đã kiểm tra danh sách, sửa tọa độ thành `null`, xóa và chặn gửi form hai lần.
- **T-10/T-11, S-05:** mã trụ unique ở cơ sở dữ liệu; kiểm mã trùng ở form và server; xử lý lỗi unique 409 kể cả khi đụng độ lúc ghi; CRUD trụ 10 vòng đã kiểm tra đầu nối và xóa dữ liệu con.
- **T-01/T-02/T-03, S-01:** Dockerfile đóng gói cả templates/static, CI được bổ sung bước build image sau lint và test, CD chỉ build/deploy sau job test. Compose vẫn dùng SQLite theo lựa chọn trước đó.
- **K-01:** đã chạy simulator mã nguồn mở trên WebSocket mock, ghi đủ Boot, Heartbeat, Status, Authorize, Start, Meter, Stop và Reset, rồi xác nhận Boot lại. Trace và bảng trường dữ liệu nằm ở `ketqua/K-01_ket_qua.md` và `ketqua/k01_trace.jsonl`.

## Kiểm chứng đã chạy

- Bộ test gần nhất: **65 passed**, có test đăng nhập cho cả năm vai trò, phân quyền, lỗi mã trụ và CRUD trạm/trụ 10 vòng.
- Alembic trên một file SQLite tạm: `upgrade head` → `downgrade base` → `upgrade head` đều thành công.
- Đọc `backend/csms.db` chỉ đọc sau các lần test: vẫn có 5 users, 5 roles, 2 stations, 3 charge points và 6 connectors; migration test dùng file tạm.
- Ruff đã tự sửa thứ tự import ở một test; bước kiểm tra cuối cùng sẽ được chạy lại sau khi chốt trạng thái đầu nối.
- JavaScript của form danh sách và API client qua `node --check`.
- K-01 chạy simulator Solidstudio tại commit `69bc17c30ef89d4a96603a0be0cb10430744b651`, bắt **26 frame** trong trace.

## Chưa thể xác nhận hoàn tất

- **Trạng thái đầu nối mới còn mâu thuẫn:** Excel S-05 yêu cầu `unknown`, còn schema T-10 trong prompt ghi `unavailable`. Hiện mã, migration và test đang tạm theo `unknown`; cần chốt lựa chọn trước khi đánh dấu S-05/T-10 hoàn tất trong workbook.
- Máy này không có Docker CLI và chưa có thông tin máy staging, nên chưa thể chạy Compose, build image cục bộ hoặc xác nhận health check/deploy/rollback trên staging. T-01/T-02/T-03 và S-01 chỉ được coi là đã cấu hình cục bộ, chưa đạt DoD staging/CI xanh.
- K-01 kiểm thử simulator với mock loopback, không chạy handler sản phẩm hay staging. Việc lưu phiên sạc thật thuộc các story tiếp theo.
- Các trang ví và lịch sử phiên là giao diện của sprint sau; API dữ liệu tương ứng chưa thuộc phạm vi Sprint 1.
