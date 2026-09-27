# Prompt triển khai Sprint 2 và rà soát Sprint 1

Đọc workbook yêu cầu chức năng ở thư mục gốc dự án, các đặc tả trong `prompts/`, cùng hướng dẫn trong `backend/skillbackend/` và `frontend/skillfrontend/`. Kiểm tra mã hiện có trước khi tiếp tục, hoàn thiện các phần backend và frontend của Sprint 2, đồng thời rà lại Sprint 1 để tìm những tiêu chí trong workbook chưa được đáp ứng.

Yêu cầu và quyết định đã chốt:

- Giữ SQLite cho môi trường phát triển cục bộ, nhưng bảo đảm chạy được cả bằng Docker Compose và `.\run.ps1` trên Windows.
- Giữ nguyên năm vai trò hiện có.
- Trạm mới bắt đầu ở trạng thái `active` theo schema T-08.
- Trạng thái `inactive` là tạm ngừng và vẫn cho trụ kết nối, báo trạng thái; `locked` là trạng thái khóa riêng do quản trị viên đặt, và BootNotification của trạm bị khóa phải bị từ chối.
- Đầu nối mới bắt đầu ở trạng thái `unavailable` theo schema T-10.
- Kiểm thử thao tác thêm, sửa, xóa dữ liệu 10 lượt; sửa lỗi phát hiện được và ghi kết quả thật. Nếu đặc tả mâu thuẫn hoặc thiếu quyết định cần thiết, dừng phần việc phụ thuộc và hỏi người dùng.
- Tạo/cập nhật tài liệu prompt và kết quả trong `ketqua/`; không commit hoặc push thay người dùng.

Khi báo cáo, phân biệt rõ phần đã triển khai và kiểm tra cục bộ với các tiêu chí cần Docker Engine, simulator, staging hoặc pipeline thật. Không đánh dấu hoàn tất các tiêu chí chưa có bằng chứng chạy.
