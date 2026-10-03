# Tổng hợp các Task đã triển khai trong Sprint 2

Dựa trên dữ liệu từ file Excel và các báo cáo nghiệm thu trong thư mục `ketqua/` (như `sprint2_completion_part1.md`, `sprint2_completion_part2.md`), dưới đây là danh sách các task thuộc Sprint 2 đã được làm xong (đạt tiêu chí cục bộ) cùng với giải thích chi tiết về việc **Đã làm gì** và **Để làm gì**.

## Nhóm 1: Kết nối OCPP và Xác thực (S-06, S-07, S-08)

### T-12 & T-13: Kết nối WebSocket và kiểm tra mã trụ
- **Đã làm gì:** Xây dựng endpoint WebSocket tại đường dẫn `/ocpp/{mã_trụ}`. Hệ thống sẽ kiểm tra xem `mã_trụ` này có tồn tại trong cơ sở dữ liệu (bảng `charge_points`) hay không. Nếu không tồn tại, kết nối bị đóng ngay lập tức và ghi log cảnh báo.
- **Để làm gì:** Đảm bảo chỉ những trụ sạc đã được chủ trạm/admin đăng ký trước trên ứng dụng web mới có thể kết nối vào hệ thống. Chặn đứng các kết nối từ thiết bị lạ để đảm bảo bảo mật.

### T-14 & T-15: Xử lý định dạng tin nhắn OCPP (CALL, CALLRESULT, CALLERROR)
- **Đã làm gì:** Viết bộ parser/packer độc lập để đọc và giải mã các mảng JSON chuẩn của giao thức OCPP 1.6J. Đồng thời tạo ra các test để kiểm tra những tin nhắn bị sai định dạng.
- **Để làm gì:** Để hệ thống CSMS hiểu được "ngôn ngữ" mà trụ sạc gửi lên. Nếu trụ sạc gửi sai chuẩn, máy chủ sẽ trả về lỗi `CALLERROR` theo đúng định dạng thay vì bị sập lỗi hệ thống, giúp kết nối mạng vẫn được giữ vững.

### T-16 & T-17: Khởi động trụ sạc (`BootNotification`)
- **Đã làm gì:** Xử lý tin nhắn `BootNotification`. Đọc các thông tin như hãng sản xuất, model, phiên bản phần mềm từ trụ sạc và lưu vào database. Trả về cho trụ trạng thái chấp nhận (`Accepted`) hoặc từ chối (`Rejected` - nếu trạm đang bị khóa) cùng với chu kỳ gửi nhịp tim.
- **Để làm gì:** Giúp hệ thống tự động ghi nhận cấu hình phần cứng của trụ sạc mỗi khi nó bật nguồn. Đồng thời thiết lập đồng hồ và dặn dò trụ sạc bao lâu thì cần gửi tín hiệu báo "tôi còn sống" (heartbeat) lên máy chủ.

## Nhóm 2: Trạng thái và Nhịp tim (S-09, S-10, S-12)

### T-18 & T-26: Quản lý nhịp tim (`Heartbeat`) và phát hiện ngoại tuyến
- **Đã làm gì:** Xử lý tin nhắn `Heartbeat` để liên tục cập nhật thời điểm liên lạc cuối (`last_seen_at`). Cấu hình một job chạy ngầm (background job) tự động quét các trụ sạc không gửi tín hiệu quá 2 chu kỳ để tự động đổi trạng thái trụ sang "Ngoại tuyến" (offline).
- **Để làm gì:** Giúp CSMS và người vận hành biết chính xác trụ sạc nào đang online và trụ nào đã bị rớt mạng, mất điện một cách tự động và kịp thời.

### T-20, T-21 & T-22: Ánh xạ trạng thái và lưu lịch sử lỗi
- **Đã làm gì:** Ánh xạ 9 trạng thái chuẩn của OCPP sang 4 trạng thái nội bộ của CSMS (rảnh, bận, đặt chỗ, lỗi). Tạo bảng `connector_errors` để lưu lại lịch sử các mã lỗi và cấu hình bỏ qua những súng sạc (đầu nối) mà chủ trạm chưa khai báo.
- **Để làm gì:** Để giao diện màn hình giám sát hiển thị trạng thái của từng súng sạc một cách đơn giản, trực quan. Việc lưu lịch sử lỗi giúp vận hành viên sau này có thể truy xuất xem trụ nào hay bị hỏng vặt nhất.

## Nhóm 3: Giao diện và Luồng thời gian thực (S-11, S-13)

### T-23, T-24 & T-25: Lưới giám sát trạm/trụ/đầu nối realtime
- **Đã làm gì:** Viết API trả về cây dữ liệu (trạm - trụ - súng sạc) có lọc theo quyền tài khoản. Làm giao diện dạng lưới ô vuông (grid) để hiển thị trụ sạc và dùng công nghệ Server-Sent Events (SSE) để đẩy trạng thái liên tục từ server xuống trình duyệt.
- **Để làm gì:** Cung cấp bảng điều khiển (dashboard) như màn hình an ninh cho người vận hành. Khi có tài xế cắm súng sạc hay trụ bị lỗi, ô màu trên màn hình sẽ tự động thay đổi ngay lập tức mà không cần người dùng phải bấm F5 (tải lại trang).

### T-28: Xử lý kết nối trùng lặp
- **Đã làm gì:** Xây dựng trình quản lý kết nối WebSocket (`ConnectionManager`) trong bộ nhớ RAM. Khi có 1 kết nối mới gửi lên trùng mã trụ với kết nối cũ đang mở, hệ thống sẽ tự đóng kết nối cũ và thay bằng kết nối mới.
- **Để làm gì:** Giải quyết triệt để tình trạng kết nối "ma" (do rớt mạng 3G/4G, trụ sạc kết nối lại nhưng server chưa kịp đóng luồng TCP cũ), đảm bảo luôn chỉ có 1 kênh duy nhất để server có thể ra lệnh xuống trụ một cách chính xác.

## Nhóm 4: Tin nhắn, Thẻ RFID và Điều khiển (S-14, S-15, S-16)

### T-30 & T-31: Lưu lịch sử tin nhắn và chống lặp
- **Đã làm gì:** Tạo bảng `ocpp_messages` lưu lại mã ID tin nhắn và câu trả lời mà server đã gửi. Thêm job tự dọn dẹp các dữ liệu cũ hơn 7 ngày.
- **Để làm gì:** Chống gửi lặp. Khi mạng chập chờn khiến trụ sạc gửi một yêu cầu 2-3 lần, CSMS sẽ nhận ra đây là yêu cầu cũ và trả lại kết quả đã xử lý từ lần trước thay vì thực hiện lại nghiệp vụ (như trừ tiền tài xế 2 lần).

### T-32 & T-33: Xác thực Thẻ RFID (`Authorize`)
- **Đã làm gì:** Tạo bảng `id_tags` quản lý thẻ RFID giao cho tài xế. Xử lý tin nhắn `Authorize` từ trụ sạc để kiểm tra thẻ đó có hợp lệ, bị khóa hay đã hết hạn hay không.
- **Để làm gì:** Cho phép tài xế dùng thẻ quẹt vật lý (RFID) quẹt trực tiếp tại trụ sạc để bắt đầu sạc thay vì phải thao tác trên app. Đảm bảo thẻ mất hoặc hết tiền sẽ bị từ chối ngay từ vòng gửi xe.

### T-34 & T-35: Khởi động lại (Reset) trụ sạc từ xa
- **Đã làm gì:** Viết hàm điều phối: gửi lệnh `CALL` từ máy chủ xuống trụ sạc và chờ nhận kết quả `CALLRESULT` (với cơ chế timeout). Tích hợp nút "Khởi động lại" (Reset mềm/cứng) trên ô giám sát trụ sạc ở giao diện Web.
- **Để làm gì:** Cung cấp "vũ khí" đầu tiên cho vận hành viên. Khi trụ bị treo hệ điều hành hoặc gặp lỗi nhỏ, vận hành viên có thể bấm nút trên Web để ra lệnh cho trụ tự khởi động lại từ xa mà không cần phải cử kỹ thuật viên chạy xe xuống tận nơi.

---
*Lưu ý:* Các task trên đều đã đạt tiêu chuẩn test nội bộ (Unit test, Integration test qua Simulator). Vài tiêu chí khắc nghiệt như "treo liên tục 50 kết nối trong 10 phút" đang chờ một môi trường Staging/Docker chuyên biệt để hoàn tất test hoàn toàn.