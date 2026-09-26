**Kết quả thực hiện Sprint 2 (Phần 1: Xác thực kết nối và nhận diện trạng thái OCPP)**

Tôi đã tiếp tục xây dựng hệ thống CSMS, hoàn thiện một phần lớn các User Story của Sprint 2:

1. **S-06: Endpoint WebSocket và xác thực mã trụ (T-12, T-13)**
- Tạo router `backend/app/routers/ocpp.py` mở endpoint WebSocket `/ocpp/{charge_point_code}`.
- Kiểm tra giao thức con (subprotocol) `ocpp1.6`, từ chối và ngắt kết nối (code 1002) nếu sai.
- Kiểm tra mã trụ từ đường dẫn với CSDL `charge_points`, từ chối kết nối mã lạ (code 1008) kèm ghi log cảnh báo.

2. **S-07: Parser và xử lý Message OCPP (T-14, T-15)**
- Xây dựng module parser độc lập `backend/app/services/ocpp_parser.py` có khả năng đọc/đóng gói 3 khung chuẩn: `CALL`, `CALLRESULT`, `CALLERROR`.
- Xây dựng bộ Unit Test kiểm chứng việc trả về đúng các mã lỗi `FormationViolation`, `ProtocolError`, `NotImplemented`.

3. **S-08 & S-09: Xử lý `BootNotification` và `Heartbeat` (T-16, T-17, T-18)**
- Xây dựng module `backend/app/services/ocpp_handlers.py`.
- Nhận diện bản tin khởi động, tự động lưu metadata (`vendor`, `model`, `firmware_version`) vào DB và đổi trạng thái trụ thành `online`.
- Tự động từ chối (`Rejected`) nếu Trạm chủ quản đang bị đánh dấu `inactive` (tạm ngừng/khoá).
- Xử lý bản tin nhịp tim, cập nhật liên tục biến `last_seen_at` và trả về giờ chuẩn UTC của máy chủ.

4. **S-10: Cập nhật trạng thái từng đầu nối (`StatusNotification`) (T-20, T-21, T-22)**
- Tạo logic ánh xạ (map) 9 trạng thái gốc OCPP sang 4 trạng thái nội bộ: `rảnh`, `bận`, `đặt chỗ`, `lỗi`.
- Thiết kế mới bảng `connector_errors` (kèm file migration) để tự động lưu lại lịch sử `errorCode`, `vendorErrorCode`, `info` mỗi khi xảy ra sự cố phần cứng.
- Cảnh báo và bỏ qua an toàn với các đầu nối (connectors) chưa từng được hệ thống khai báo.

**Tất cả các chức năng đã được viết kèm đầy đủ Unit Test (25 bài test tự động)** bằng `pytest`, sử dụng In-Memory SQLite để đảm bảo tách biệt tuyệt đối với Database gốc của dự án. Mọi bài test đều đã Passed 100%.

*Sẵn sàng để triển khai tiếp các phần còn lại của Sprint 2 (S-11, S-12, S-13, S-14, S-15, S-16).*
