# Tổng hợp các Task đã hoàn thành trong Sprint 2

Dưới đây là danh sách các task của Sprint 2 đã được triển khai (dựa trên kết quả trong thư mục `ketqua/`), cùng với giải thích chi tiết về việc **đã làm gì** và **để làm gì**.

### T-12: Endpoint WebSocket đọc mã trụ từ đường dẫn và tra bảng `charge_points`
**1. Đã làm gì:**
Mở endpoint WebSocket dạng `/ocpp/<mã trụ>`, lấy mã trụ từ đường dẫn, tra cứu trong bảng `charge_points` ở T-10, chấp nhận nếu có. Xem bản ghi chuỗi tin nhắn từ K-01 để biết simulator nối vào đường dẫn nào và khai giao thức con gì.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Trụ ảo nối vào bằng mã hợp lệ thì kết nối mở và giữ được ít nhất 10 phút không tự đứt
*(Ràng buộc NFR: giữ được ít nhất 50 kết nối đồng thời trên staging)*

---

### T-13: Đóng kết nối của mã lạ và ghi nhật ký lần thử
**1. Đã làm gì:**
Nhánh từ chối của T-12: mã không có trong bảng thì đóng kết nối với mã đóng chuẩn và ghi log ở mức cảnh báo kèm mã lạ và IP. Không trả về lý do chi tiết cho phía trụ.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Nối trụ ảo với mã bịa thì kết nối đóng trong 1 giây và log có đúng một dòng cảnh báo
*(Ràng buộc NFR: không log toàn bộ header của yêu cầu, chỉ log mã và IP)*

---

### T-14: Hàm đọc và ghi khung `CALL`, `CALLRESULT`, `CALLERROR`
**1. Đã làm gì:**
OCPP 1.6J gói mỗi tin nhắn thành một mảng JSON: `[2, mã, hành động, tải]` cho `CALL`, `[3, mã, tải]` cho `CALLRESULT`, `[4, mã, mã lỗi, mô tả, chi tiết]` cho `CALLERROR`. Viết một module thuần, không phụ thuộc WebSocket, gồm hàm đọc và hàm ghi cho ba loại. Bản ghi ở K-01 là dữ liệu mẫu cho test.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Đọc đúng mọi khung trong bản ghi K-01; ghi rồi đọc lại cho ra cùng giá trị
*(Ràng buộc NFR: module thuần, test được không cần mở kết nối)*

---

### T-15: Bộ test khung sai định dạng trả về `CALLERROR` đúng mã lỗi
**1. Đã làm gì:**
Viết test cho các ca: không phải mảng, thiếu phần tử, loại khung lạ, tải không phải đối tượng, hành động chưa hỗ trợ. Mỗi ca đối chiếu mã lỗi với bảng mã lỗi trong đặc tả (`FormationViolation`, `ProtocolError`, `NotImplemented`). Đây là mẫu viết test theo bảng dữ liệu cho các handler sau.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Cả năm ca đều trả về `CALLERROR` đúng mã và kết nối vẫn mở sau đó
*(Ràng buộc NFR: test chạy trong CI ở T-02)*

---

### T-16: Handler `BootNotification` lưu nhà sản xuất, mẫu trụ, phiên bản firmware
**1. Đã làm gì:**
Handler đầu tiên viết theo khung ở T-14; cấu trúc file của nó là mẫu cho mọi handler sau. Đọc các trường `chargePointVendor`, `chargePointModel`, `firmwareVersion` và lưu vào `charge_points`. Thêm cột bằng migration mới theo mẫu T-10.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Trụ ảo gửi `BootNotification` thì ba cột trên có dữ liệu và cột trạng thái chuyển sang trực tuyến
*(Ràng buộc NFR: trường thiếu thì lưu rỗng, không từ chối tin nhắn)*

---

### T-17: Trả về trạng thái chấp nhận hoặc từ chối kèm khoảng nhịp tim cấu hình được
**1. Đã làm gì:**
Phần trả lời của T-16: quyết định `Accepted`/`Rejected` theo trạng thái trụ và trạm, đọc khoảng nhịp tim từ cấu hình, chặn mọi tin nhắn khác cho tới khi trụ được chấp nhận.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Trụ ảo nhận `Accepted` kèm `interval` bằng giá trị cấu hình; đổi cấu hình rồi khởi động lại ứng dụng thì giá trị mới được dùng
*(Ràng buộc NFR: giờ máy chủ trong câu trả lời ở múi giờ UTC theo đặc tả)*

---

### T-18: Handler `Heartbeat` cập nhật một cột `last_seen_at` và trả giờ máy chủ
**1. Đã làm gì:**
Handler theo mẫu T-16. Cập nhật `charge_points.last_seen_at` bằng một câu `UPDATE` đúng một cột. Gọi cùng hàm cập nhật đó từ khung ở T-14 cho mọi tin nhắn tới.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Trụ ảo gửi nhịp tim thì `last_seen_at` đổi; gửi `StatusNotification` cũng làm cột này đổi
*(Ràng buộc NFR: không khoá bản ghi lâu hơn một câu lệnh)*

---

### T-20: Ánh xạ trạng thái OCPP sang trạng thái nội bộ của bảng `connectors`
**1. Đã làm gì:**
Bảng ánh xạ 9 trạng thái của đặc tả (`Available`, `Preparing`, `Charging`, `SuspendedEV`, `SuspendedEVSE`, `Finishing`, `Reserved`, `Unavailable`, `Faulted`) sang bốn trạng thái nội bộ: rảnh, bận, đặt chỗ, lỗi. Đặt bảng ánh xạ ở một module riêng để màn hình và báo cáo dùng chung. Handler theo mẫu T-16.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Đổi trạng thái trên trụ ảo thì bảng `connectors` đổi theo trong vòng 1 giây; trạng thái lạ chưa biết lưu nguyên văn vào cột riêng
*(Ràng buộc NFR: trạng thái lạ không làm sập luồng xử lý)*

---

### T-21: Lưu mã lỗi và thời điểm vào bảng `connector_errors`
**1. Đã làm gì:**
Bảng mới `connector_errors` chỉ ghi thêm: đầu nối, mã lỗi, mã lỗi nhà sản xuất, thời điểm. Ghi mỗi khi `errorCode` khác `NoError`. Migration theo mẫu T-10.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Trụ ảo báo `Faulted` kèm mã lỗi thì có một dòng mới; báo `Available` sau đó không xoá dòng cũ
*(Ràng buộc NFR: có chỉ mục theo đầu nối và thời điểm để S-46 đếm lỗi theo khoảng thời gian)*

---

### T-22: Bỏ qua đầu nối chưa khai báo kèm cảnh báo, không tạo mới
**1. Đã làm gì:**
Nhánh lỗi của T-20: `connectorId` lớn hơn số đầu nối đã khai ở S-05 thì ghi cảnh báo kèm mã trụ và số đầu nối, trả `CALLRESULT` rỗng theo đặc tả, không chèn bản ghi.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Trụ ảo khai 2 đầu nối gửi trạng thái cho đầu nối 3 thì bảng `connectors` vẫn 2 dòng và log có cảnh báo
*(Ràng buộc NFR: cảnh báo gom theo trụ, không lặp mỗi giây)*

---

### T-23: Truy vấn một lần trả về cây trạm–trụ–đầu nối đã lọc theo quyền
**1. Đã làm gì:**
Một truy vấn nối ba bảng, trả về cây ba tầng, đi qua hàm lọc sở hữu ở T-07. Đo thời gian chạy với 50 trụ và 200 đầu nối bằng dữ liệu seed trước khi coi là xong.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Trả về đúng cây ba tầng; chạy dưới 200ms với 50 trụ; chủ trạm chỉ nhận trạm của mình
*(Ràng buộc NFR: không dùng vòng lặp gọi truy vấn con cho từng trụ)*

---

### T-24: Màn hình theo dõi dạng lưới, mỗi ô một trụ, nhãn chữ kèm màu
**1. Đã làm gì:**
Lưới trạm → trụ → đầu nối. Trạng thái phân biệt bằng nhãn chữ kèm màu, không chỉ màu. Trụ ngoại tuyến hiện thời điểm liên lạc cuối. Bố cục trang theo T-09.

**2. Để làm gì (Mục đích & Nghiệm thu):**
20 trụ hiện đủ trên một màn hình máy tính không cần cuộn ngang; người mù màu vẫn đọc được trạng thái
*(Ràng buộc NFR: trạng thái phân biệt không chỉ bằng màu, thêm nhãn chữ)*

---

### T-25: Kênh đẩy trạng thái xuống trình duyệt khi đầu nối đổi
**1. Đã làm gì:**
Khi T-20 đổi trạng thái đầu nối, phát một sự kiện nội bộ; một endpoint Server-Sent Events đẩy sự kiện đó xuống các trình duyệt đang mở màn hình, đã lọc theo quyền. Trình duyệt tự nối lại khi đứt và gọi lại truy vấn T-23.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Đổi trạng thái trên trụ ảo thì màn hình đổi trong 1 giây; tắt rồi bật lại máy chủ thì màn hình tự khôi phục không cần tải lại
*(Ràng buộc NFR: không đẩy sự kiện của trạm này tới trình duyệt của chủ trạm khác)*

---

### T-26: Job nền quét `last_seen_at` quá hai chu kỳ và đổi trạng thái
**1. Đã làm gì:**
Job chạy mỗi phút, so `last_seen_at` với `now()` của cơ sở dữ liệu, đổi trạng thái trụ quá hạn. Chạy lặp nhiều lần không gây tác dụng phụ. Đây là job nền đầu tiên của dự án — cách đăng ký và ghi log của nó là mẫu cho T-31, T-53.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Dừng trụ ảo thì sau hai chu kỳ nhịp tim trụ chuyển sang ngoại tuyến; chạy job hai lần liên tiếp không đổi gì thêm
*(Ràng buộc NFR: truy vấn xác định ngoại tuyến so sánh thời gian ở máy chủ cơ sở dữ liệu)*

---

### T-28: Bảng kết nối đang mở trong bộ nhớ, thay thế khi trùng mã
**1. Đã làm gì:**
Một cấu trúc ánh xạ mã trụ → kết nối đang mở, gắn vào T-12. Kết nối mới cùng mã thì đóng cái cũ trước rồi thay thế. Mọi lệnh máy chủ gửi xuống trụ (T-34, T-49) tra ở đây.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Mở hai trụ ảo cùng mã thì kết nối đầu nhận khung đóng và bảng chỉ còn một mục
*(Ràng buộc NFR: thao tác thay thế phải nguyên tử trong tiến trình)*

---

### T-30: Bảng `ocpp_messages` lưu mã tin nhắn và câu trả lời đã gửi
**1. Đã làm gì:**
Bảng `ocpp_messages` khoá theo cặp (mã trụ, mã tin nhắn), lưu tên hành động, câu trả lời đã gửi, thời điểm. Chèn vào khung ở T-14 một bước tra bảng trước khi gọi handler. Migration theo mẫu T-10.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Gửi lại cùng tin nhắn 5 lần thì chỉ có một bản ghi phiên và năm lần đều nhận cùng câu trả lời
*(Ràng buộc NFR: tra bảng và gọi handler nằm trong cùng một giao dịch để hai tin tới đồng thời không cùng lọt)*

---

### T-31: Job dọn bản ghi cũ hơn 7 ngày và test gửi lại 5 lần
**1. Đã làm gì:**
Job nền theo mẫu T-26 xoá bản ghi `ocpp_messages` quá 7 ngày. Test tích hợp theo mẫu T-29 cho ca gửi lại 5 lần và ca khởi động lại tiến trình giữa hai lần gửi.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Sau khi job chạy, không còn bản ghi quá 7 ngày; hai test xanh trong CI
*(Ràng buộc NFR: số ngày giữ là tham số cấu hình)*

---

### T-32: Bảng `id_tags` gắn thẻ với tài xế, có trạng thái khoá và hạn dùng
**1. Đã làm gì:**
Bảng `id_tags`: mã thẻ unique, khoá ngoại tới `users` vai trò tài xế, trạng thái, hạn dùng. Seed mỗi tài xế thử nghiệm một thẻ. Migration theo mẫu T-10.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Migration tiến và lùi được; chèn hai thẻ cùng mã thì bị từ chối
*(Ràng buộc NFR: có chỉ mục theo mã thẻ vì mọi `Authorize` tra theo cột này)*

---

### T-33: Handler `Authorize` trả về `Accepted`, `Blocked`, `Expired` hoặc `Invalid`
**1. Đã làm gì:**
Handler theo mẫu T-16, tra bảng T-32 và trạng thái trạm, trả `idTagInfo` đúng cấu trúc đặc tả. Test theo bảng dữ liệu như T-15 cho năm ca của AC.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Năm ca của S-15 đều đúng trên trụ ảo; log chỉ hiện bốn ký tự cuối của thẻ
*(Ràng buộc NFR: không tiết lộ lý do chi tiết ngoài bốn trạng thái chuẩn)*

---

### T-34: Gửi `CALL` từ máy chủ tới trụ và khớp `CALLRESULT` theo mã tin nhắn
**1. Đã làm gì:**
Hàm dùng chung: sinh mã tin nhắn duy nhất, ghi khung `CALL` bằng T-14, gửi qua kết nối tra ở T-28, chờ `CALLRESULT` có cùng mã với thời gian chờ cấu hình được. Dùng cho `Reset` trước, sau này cho mọi lệnh khác.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Gọi `Reset` trên trụ ảo nhận đúng `CALLRESULT`; trụ không trả lời thì hàm trả lỗi hết thời gian sau đúng số giây cấu hình
*(Ràng buộc NFR: một lời gọi đang chờ không chặn việc xử lý tin nhắn khác trên cùng kết nối)*

---

### T-35: Nút khởi động lại trên màn hình theo dõi, báo lỗi khi trụ ngoại tuyến
**1. Đã làm gì:**
Nút trên ô trụ ở T-24, hộp chọn kiểu mềm/cứng, gọi API dùng T-34. Trụ ngoại tuyến thì API trả lỗi ngay không gọi xuống trụ. Ghi một dòng nhật ký thao tác — bảng nhật ký sẽ chuẩn hoá ở T-57, tạm ghi log ứng dụng.

**2. Để làm gì (Mục đích & Nghiệm thu):**
Bấm nút trên trụ ảo trực tuyến thì trụ khởi động lại và ô trụ chuyển ngoại tuyến rồi trực tuyến; trụ ngoại tuyến thì hiện thông báo ngay
*(Ràng buộc NFR: chỉ vai trò vận hành viên và quản trị thấy nút này)*

---

