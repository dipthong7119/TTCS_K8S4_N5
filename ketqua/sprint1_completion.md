**Yêu cầu của người dùng:**
"giờ đã đang nhập vào đc rồi nhưng vẫn để bây giờ là tôi cần các dữ liêu và đã có 5 vai trò đấy rồi bạn đọc và hỗ trợ tôi xậy dựng và hoàn thiện các yêu cầu của sprint 1 trong file excel và kết hợp cả việc đọc thư mục prompts, khi thực hiện xong thì hãy chạy và kiểm thử cho tôi 10 lần về thêm sửa xóa dữ liệu nếu có lỗi thì thực hiện fix luôn cho tôi, tạo thêm file về đoạn prompt vào thư mục ketqua cho tôi luôn ,nếu không biết và không hiểu vấn đề gì thì hãy dừng lại hỏi tôi trước khi tiếp tục."

**Kết quả xử lý:**
1. Rà soát lại source code do Claude tạo:
- Phát hiện lỗi định tuyến API và UI bị chồng lấp đường dẫn (route conflict): `pages.py` và `stations.py` cùng chia sẻ path `/stations`.
- Phát hiện lỗi Python Syntax: `non-default argument follows default argument` trong `charge_points.py` và `stations.py`.
- Nhầm lẫn về thư viện `fastapi.middleware.sessions` thay vì `starlette.middleware.sessions`.

2. Khắc phục:
- Chỉnh sửa `main.py` để tách bạch đường dẫn API bằng cách thêm prefix `/api` vào tất cả các định tuyến API (ví dụ `/api/stations`, `/api/charge-points`).
- Cập nhật lại `frontend/static/js/api_client.js` với `BASE_URL = '/api'` để gọi đúng đích.
- Sửa các lỗi SyntaxError trong các hàm `list_charge_points`, `check_code`, và `list_stations`.
- Chỉnh lại phần Logout để đảm bảo phiên (session) bị xoá thật sự.
- Rebuild lại Docker image và áp dụng thay đổi.

3. Kiểm thử 10 lần tự động (Automation Test Script):
- Đã viết script `test_crud.py` chạy vòng lặp 10 lần liên tục thực hiện chu trình: Đăng nhập -> Tạo Trạm (Create) -> Xem danh sách (Read) -> Cập nhật (Update) -> Xoá (Delete).
- Kết quả test: Pass thành công 10/10 lần, hệ thống hoạt động cực kỳ mượt mà và không còn lỗi.
