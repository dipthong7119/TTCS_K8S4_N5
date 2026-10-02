# Prompt tiếp tục hoàn thiện Sprint 1 CSMS

Bạn là cộng sự lập trình cho dự án CSMS tại `E:\TTCS_K8S4_N5`. Trước khi sửa mã, hãy đọc workbook Sprint 1 trong thư mục gốc, `prompts/00_QUY_TAC_AGENT.md`, `prompts/01_CODEBASE_MAP.md`, `prompts/02_DAC_TA_DU_AN.md`, `prompts/SPRINT_1.md` và các hướng dẫn trong thư mục `skill/` có liên quan. Sau đó xem `git status`, mã nguồn và báo cáo trong `ketqua/` để tiếp tục đúng phần còn thiếu; giữ nguyên mọi thay đổi người dùng đã có.

## Phạm vi

- Đối chiếu các mục T-01 đến T-11 và K-01 trong workbook với đặc tả và chương trình hiện tại.
- Hoàn thiện luồng đăng nhập, năm vai trò, từ chối mặc định cho route chưa khai quyền, lọc dữ liệu theo chủ sở hữu, CRUD trạm, trụ sạc và đầu nối, kiểm tra mã trụ trùng, giao diện tạo/sửa và simulator OCPP 1.6J.
- Tạo hoặc cập nhật test cho hành vi thay đổi. Chạy riêng cả test gốc và test backend; chạy Ruff như pipeline CI.
- Chạy 10 vòng CRUD trạm và 10 vòng CRUD trụ sạc, xác nhận sau mỗi vòng rằng tạo, đọc, sửa, xóa và kiểm tra trùng mã hoạt động đúng. Nếu test hỏng, tìm nguyên nhân, sửa rồi chạy lại.
- Cập nhật `ketqua/sprint1_completion.md` bằng kết quả đã kiểm chứng và nêu rõ giới hạn môi trường.

## Quyết định đã xác nhận

- Giữ SQLite cho phát triển cục bộ; không đổi URL, migrate, xóa hoặc seed vào database thật của người dùng. Dùng database tạm riêng cho mọi test.
- Trạng thái mặc định của trạm mới là `active`, theo schema T-08; người dùng đã chọn phương án này khi AC S-04 có câu chữ mâu thuẫn.
- Workbook là tài liệu yêu cầu. Không tự đổi trạng thái backlog hay sửa nội dung workbook nếu chưa được yêu cầu.
- Không đọc hoặc in giá trị bí mật từ `.env`.

## Cách làm và báo cáo

Tuân theo quy tắc dự án về vị trí file, migration, quyền truy cập và không tạo thư mục/file phiên bản song song. Nếu đặc tả có mâu thuẫn mới hoặc thiếu quyết định ảnh hưởng dữ liệu, dừng phần phụ thuộc vào quyết định đó và hỏi người dùng; vẫn tiếp tục các phần độc lập. Không tuyên bố Docker, PostgreSQL hoặc staging đã xác minh nếu chưa chạy được thật. Cuối cùng liệt kê thay đổi, số test pass/fail, kết quả 10 vòng CRUD, và các phần chưa thể kiểm chứng.
