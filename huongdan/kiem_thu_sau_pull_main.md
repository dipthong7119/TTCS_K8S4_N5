# Kiểm thử web sau đồng bộ main

Ngày 06/10/2026, đồng bộ `ea94972` → `bff0369` (13 commit), giữ T-55 và cấu trúc
thư mục đã sắp xếp trên máy. App Docker đang phục vụ tại <http://localhost:8000>.

## Bổ sung sau gộp DANG-DAI (06/10/2026)

Đã gộp đầu nhánh `34a9b4d` bằng commit local `55d58a7`. Giữ các thay đổi local
T-55, bộ lọc từng trụ, nút đóng chi tiết và phiên bản tài nguyên.

| Task | Phần nhận được | Kết luận sau kiểm tra |
| --- | --- | --- |
| SCRUM-135 (Sprint 2) | Đăng nhập, hiện/ẩn mật khẩu và thông báo lỗi đã có trước gộp. Nhánh chỉnh validation, kiểm tra quyền cho `next`, ApiClient và thêm `/api/auth/me`. | Là cải tiến phần đã có, không phải chức năng đăng nhập mới. Đã kiểm thử với 5 vai trò. |
| SCRUM-190 (T-52, Sprint 3) | Chọn đầu nối Available của trụ online và nút Bắt đầu sạc. | Có giao diện thử; chưa gửi lệnh sạc hay tạo phiên. |
| SCRUM-191 | Có đoạn đếm ngược trong nhánh nhưng không có yêu cầu nào được đưa vào trạng thái chờ. | Chưa hoàn thành; không đưa timer chưa sử dụng vào trang local. |
| SCRUM-192 | Cần phản hồi từ chối, trụ bận và hết thời gian. | Chưa có luồng xử lý các phản hồi này. |
| SCRUM-194 | Cần kiểm thử đầy đủ luồng bắt đầu sạc. | Chưa thể kết luận Done; hiện chỉ kiểm chứng UI thử. |

Phần cần kiểm tra sau đồng bộ:

1. Nhấn F5, mở `/login`: kiểm tra lại đăng nhập và nút mắt đã có.
   Đã gỡ chế độ đăng nhập giả và dòng hướng dẫn mock ngoài yêu cầu.
   URL cũ `/login?mock=1` cũng sử dụng API đăng nhập thông thường.
   Các thử nghiệm khóa sau nhiều lần sai đã chạy với DB tạm; không cần cố tình
   khóa tài khoản/IP của app đang dùng.
2. Mở `/monitoring`, chọn **Sẵn sàng**, bấm trụ `CP_VINCOM_01` hoặc một trụ SIM.
   Trong chi tiết, chọn **Đầu nối 1/2**, bấm **Bắt đầu sạc**. Thông báo ghi rõ
   đây là bản thử và chưa gửi yêu cầu; không có phiên mới xuất hiện.
3. Chọn **Lỗi**: chỉ `CP_AEON_FAULT` hiện; đầu nối của trụ lỗi không chọn được.
   Chọn **Tạm ngừng / Bảo trì**: đầu nối bảo trì cũng không chọn được.
4. Đóng chi tiết bằng X, bấm ngoài hoặc Esc; đổi lưới/danh sách, bỏ lọc và bấm
   Làm mới. Các thao tác cũ vẫn hoạt động.

T-52 phụ thuộc API T-51/SCRUM-193 và luồng phản hồi từ trụ. Đợt đồng bộ này
không triển khai tiếp các task đó. Xem kết quả và phạm vi Git ở
`ketqua/dong_bo_main.md`.

## Thay đổi vừa lấy từ main

| Phần | Thay đổi thực tế | Cách quan sát |
| --- | --- | --- |
| T-36 / SCRUM-161 | Bổ sung test migration của bảng phiên, ràng buộc một phiên mở trên một đầu nối và mã phiên do DB cấp. Schema này đã có từ trước. | Xem danh sách/chi tiết phiên trên `/sessions`; các ràng buộc DB đã kiểm thử tự động. |
| T-37 / SCRUM-162 | Tách `StartTransaction` từ service chung sang handler riêng, bổ sung test tạo phiên, thẻ sai, phiên trùng và tin nhắn gửi lại. | Khi trụ gửi StartTransaction hợp lệ, phiên được ghi nhận và đầu nối chuyển sang đang sạc. |
| T-38 / SCRUM-163 | Tách `StopTransaction` sang handler riêng; bổ sung test đóng phiên, số kWh và gửi lại tin nhắn không đóng phiên hai lần. | Sau StopTransaction hợp lệ, chi tiết phiên thể hiện thời điểm kết thúc và kWh. |
| SCRUM-187 | Bổ sung đáp án tính tay cho hàm tính kWh: tăng, giảm, bằng nhau và phần Wh lẻ. Hàm tính đã có từ trước. | Xem kWh của phiên đã kết thúc. |
| API phiên hiện tại | Eager-load hóa đơn cùng phiên/số đo, tránh truy vấn bổ sung khi serialize. | Tài xế mở `/sessions/mine`; API `/api/sessions/current` trả 204 khi chưa có phiên đang chạy. |

Đợt pull này không thêm template, JS hoặc trang web mới. Các handler giữ luồng
nghiệp vụ đã có; thay đổi chủ yếu là tổ chức backend, kiểm thử và truy vấn API.

## Tài khoản development

Đây là tài khoản mẫu đã công khai trong README, chỉ dùng kiểm thử local.

| Vai trò | Email | Mật khẩu mẫu |
| --- | --- | --- |
| Quản trị | `admin@csms.local` | `Admin@2024!` |
| Vận hành | `operator@csms.local` | `Operator@2024!` |
| Tài xế | `driver@csms.local` | `Driver@2024!` |

## Các bước thử trực tiếp

1. Mở <http://localhost:8000/login>, đăng nhập quản trị hoặc vận hành.
2. Mở <http://localhost:8000/monitoring>; trang luôn dùng dữ liệu API/SSE.
   Máy hiện bật thêm `CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS=true`, nên cả
   **25 trụ / 49 đầu nối** đều kết nối. Trụ AEON lỗi giữ `GroundFailure`, trụ
   Thủ Thiêm có hai đầu nối tạm ngừng để thử bộ lọc lỗi/bảo trì.
   Chọn **Lỗi**: chỉ hiện `CP_AEON_FAULT`, không có trụ khỏe `CP_AEON_01`
   cùng trạm. Chọn **Tạm ngừng / Bảo trì**: chỉ hiện `CP_DEMO_MAINT_01`.
   Mở chi tiết và đổi dạng lưới/danh sách vẫn giữ đúng các trụ khớp.
   Ô tổng lỗi hiển thị **1 trụ**, không tính trụ bảo trì và không đếm trùng đầu nối.
   Nút **Dữ liệu mẫu (20 trụ)** đã bỏ; dữ liệu mô phỏng đến từ simulator Docker.
   Nếu đang mở trang cũ, nhấn **F5**. URL JS/CSS tự đổi phiên bản khi file thay đổi,
   nên trình duyệt tải đúng code mới; không cần xóa cache thủ công.
   Mở trạm thử nghiệm OCPP: `SIM-01` đến `SIM-20` online; dữ liệu đến từ các
   client WebSocket trong Docker. Mở chi tiết một trụ và thử Reset Soft, chờ
   trụ nối lại. Có thể thử Reset Hard theo cùng cách.
3. Mở <http://localhost:8000/sessions>, đổi bộ lọc thời gian/trạng thái và bấm
   một phiên để xem đầu nối, thời gian bắt đầu/kết thúc, kWh và lý do dừng.
   Dữ liệu mẫu cố ý nằm ở các ngày khác nhau; chọn khoảng dài hơn nếu danh sách ít.
4. Mở <http://localhost:8000/sessions/anomalies>, thử bộ lọc lý do/khoảng ngày.
   Danh sách trống là hợp lệ nếu dữ liệu hiện có không chứa phiên bất thường.
5. Mở <http://localhost:8000/audit>, lọc theo trụ/người/khoảng thời gian.
   Sau khi thử Reset, xem nhật ký thao tác tương ứng.
6. Đăng xuất, đăng nhập tài xế và mở <http://localhost:8000/sessions/mine>.
   Chỉ thấy phiên của tài xế đó. Tại lúc kiểm tra, tài xế mẫu không có phiên
   đang chạy nên API current trả **204**, không phải lỗi.

T-55 hiện gửi BootNotification, StatusNotification cho mọi đầu nối đã khai báo,
Heartbeat và trả lời Reset; dùng được cả trụ SIM và 5 trụ của các trạm mẫu.
Fleet mặc định không tự chạy phiên sạc hoặc xử lý RemoteStart/RemoteStop.
Vì vậy việc tạo/đóng phiên qua các handler mới phải dùng client phát các tin nhắn
StartTransaction/MeterValues/StopTransaction; các ca này đã được kiểm thử tự động.
Nút dừng từ xa chưa thể kiểm chứng thành công với fleet T-55 mặc định.

Nếu Docker đã được dừng, chạy từ thư mục gốc để bật lại fleet theo cấu hình `.env`:

```powershell
docker compose --profile ocpp-simulator up -d --build simulator
```
