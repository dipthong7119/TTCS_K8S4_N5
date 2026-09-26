# K-01 — Trace simulator OCPP 1.6J

## Kết luận

Đã chạy một phiên OCPP hoàn chỉnh từ khởi động trụ đến dừng phiên và Reset. Simulator nối vào một máy chủ WebSocket mock chỉ chạy trên loopback; máy chủ mock phản hồi các khung OCPP và ghi nguyên frame trao đổi. Trace thực tế có trong [k01_trace.jsonl](k01_trace.jsonl). Không kết nối tới CSMS sản phẩm và không dùng cơ sở dữ liệu ứng dụng.

## Simulator và cách chạy

- **Dự án:** [Solidstudio OCPP Virtual Charge Point](https://github.com/solidstudiosh/ocpp-virtual-charge-point), hỗ trợ OCPP 1.6J, có các lệnh điều khiển thử `Authorize`, `StartTransaction`, `MeterValues`, `StopTransaction` và tự gửi `BootNotification`, `StatusNotification`, `Heartbeat`.
- **Giấy phép:** Apache-2.0.
- **Phiên bản đã thử:** commit `69bc17c30ef89d4a96603a0be0cb10430744b651`.
- **Máy chủ thử:** WebSocket mock chỉ bind loopback; simulator đàm phán subprotocol `ocpp1.6`. Kịch bản dùng token thử `K01-DEMO-TAG`, cấp transaction ID `51001`, gửi Reset Soft và xác nhận trụ kết nối lại rồi Boot lần nữa.

Repo nguồn simulator không được chép vào dự án; trace JSONL là bản ghi frame nguyên gốc sau khi chạy spike.

## Chuỗi frame đã quan sát

Các cặp request/response dưới đây lấy từ trace ghi trực tiếp; `uniqueId` và timestamp đầy đủ nằm trong JSONL.

| Bước | Hướng | CALL và kết quả |
|---|---|---|
| Khởi động | Trụ → CSMS → trụ | `BootNotification` (`Solidstudio`, `VirtualChargePoint`, serial `S001`, firmware `1.0.0`) → `Accepted`, chu kỳ Heartbeat 1 giây |
| Báo trạng thái | Trụ → CSMS → trụ | `StatusNotification` connector 1, `Available`, `NoError` → `{}` |
| Nhịp sống | Trụ → CSMS → trụ | `Heartbeat` → `currentTime` của CSMS |
| Xác thực thẻ | Trụ → CSMS → trụ | `Authorize` với `K01-DEMO-TAG` → `Accepted` |
| Bắt đầu phiên | Trụ → CSMS → trụ | `StartTransaction`, connector 1, `meterStart=0` → `transactionId=51001`, `Accepted` |
| Số đo | Trụ → CSMS → trụ | `MeterValues`, transaction 51001, công suất `7.2 kW`, năng lượng `0.02 kWh` → `{}` |
| Rút súng/dừng phiên | Trụ → CSMS → trụ | `StopTransaction`, transaction 51001, `meterStop=20 Wh`, reason `EVDisconnected` → `{}` |
| Khởi động lại | CSMS → trụ → CSMS | `Reset` kiểu `Soft` → trụ trả `Accepted`, đóng WebSocket, kết nối lại và gửi `BootNotification` lần nữa |

Harness còn ghi các Heartbeat và StatusNotification xuất hiện xung quanh các bước trên; trace hiện lưu tổng cộng 26 frame.

## Trường OCPP cần xử lý và lưu

| Tin nhắn | Request fields | Response fields | Dữ liệu nên giữ cho các story sau |
|---|---|---|---|
| `BootNotification` | `chargePointVendor`, `chargePointModel`; tùy chọn `chargePointSerialNumber`, `chargeBoxSerialNumber`, `firmwareVersion`, `iccid`, `imsi`, `meterType`, `meterSerialNumber` | `currentTime`, `interval`, `status` | Mã trụ, hãng/model/firmware, trạng thái Boot, timestamp máy chủ và `last_seen_at` |
| `Heartbeat` | Không có field | `currentTime` | Mã trụ và giờ nhận ở CSMS; cập nhật `last_seen_at` theo đồng hồ máy chủ |
| `StatusNotification` | `connectorId`, `errorCode`, `status`; tùy chọn `timestamp`, `info`, `vendorId`, `vendorErrorCode` | Object rỗng | Mã trụ, đầu nối, trạng thái chuẩn, mã lỗi, thông tin lỗi, timestamp nguồn và timestamp nhận |
| `Authorize` | `idTag` | `idTagInfo.status`; tùy chọn `expiryDate`, `parentIdTag` | Kết quả tra thẻ, thời điểm kiểm tra, mã thẻ dưới dạng tham chiếu được bảo vệ; tránh ghi toàn bộ mã thẻ vào log |
| `StartTransaction` | `connectorId`, `idTag`, `meterStart`, `timestamp`; tùy chọn `reservationId` | `transactionId`, `idTagInfo` | Mã trụ/đầu nối, tham chiếu tài xế và thẻ, số đo đầu, giờ bắt đầu, transaction ID, kết quả xác thực |
| `MeterValues` | `connectorId`; tùy chọn `transactionId`; `meterValue[]` gồm timestamp và `sampledValue[]` (`value`, tùy chọn `context`, `format`, `measurand`, `phase`, `location`, `unit`) | Object rỗng | ID phiên/đầu nối, thời điểm mẫu, từng measurand, giá trị, đơn vị và metadata mẫu |
| `StopTransaction` | `transactionId`, `meterStop`, `timestamp`; tùy chọn `idTag`, `reason`, `transactionData[]` | Tùy chọn `idTagInfo` | Phiên, số đo cuối, giờ kết thúc, lý do dừng, số đo cuối phiên và trạng thái thẻ nếu có |
| `Reset` | `type` (`Hard` hoặc `Soft`) | `status` (`Accepted` hoặc `Rejected`) | Mã trụ, loại lệnh, kết quả gửi lệnh, thời điểm gửi/nhận và thời điểm kết nối lại |

`transactionId` do CSMS cấp trong phản hồi `StartTransaction`. Các mẫu `MeterValues` có cấu trúc lồng nhau; cần lưu riêng từng `sampledValue` để truy vấn theo measurand và thời gian. Timestamp trụ gửi và timestamp CSMS nhận nên được giữ riêng để phát hiện đồng hồ trụ lệch.

## Phạm vi và giới hạn

K-01 là spike giao thức và tài liệu dữ liệu; trace xác nhận simulator mã nguồn mở trao đổi đủ các loại tin nhắn được yêu cầu với WebSocket mock. Mock không kiểm thử handler sản phẩm, xác thực thiết bị, lưu phiên vào DB hay staging. Các handler nghiệp vụ Start/Meter/Stop thuộc các story kế tiếp; không đánh dấu chúng là đã hoàn tất chỉ dựa trên spike này. OCPP 1.6 được Open Charge Alliance công bố từ năm 2015; bộ specification tải từ [trang OCPP chính thức của OCA](https://openchargealliance.org/my-oca/ocpp/).
