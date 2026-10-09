# Phân công công việc – SCRUM Sprint 345 (bản cập nhật)

**Thời gian Sprint:** 9/10 – 31/10 | **Mục tiêu:** hoàn thành toàn bộ trong 1 tuần | **Số work item:** 26 | **Tổng story point:** 64

> Đây là bản đề xuất phân công đã chia lại để hoàn thành trong 1 tuần: bớt việc cho những người đang nằm trên đường găng (Ngô, Tân, Vinh, Đức) và chuyển sang cho **Scrum Master (Trịnh Thanh Tùng)** những phần độc lập hoặc cùng mảng kiểm thử. Cả nhóm có thể điều chỉnh lại khi họp Sprint Planning.

---

## 1. Thành viên và vai trò

| Vai trò | Thành viên |
|---|---|
| Scrum Master | Trịnh Thanh Tùng |
| Backend Developer | Ngô Quang Tùng, Nguyễn Lâm Tùng, Hoàng Văn Tân, Tạ Như Vinh, Hoàng Văn Đức |
| Frontend Developer | Phạm Văn Tuấn, Vy Hoàng Tú, Đặng Ngọc Đại |
| Kiểm thử / review | Các thành viên tự kiểm thử và review chéo |

## 2. Các Epic trong Sprint

| Epic | Các work item |
|---|---|
| Kết nối OCPP và phiên sạc | SCRUM-53 → 59, SCRUM-60 |
| Giám sát vận hành | SCRUM-89 |
| Ứng dụng tài xế | SCRUM-94, SCRUM-95 |
| Biểu giá và tính tiền | SCRUM-61 → 68 |
| Ví và thanh toán | SCRUM-69 → 75 |

---

## 3. Bảng tổng hợp phân công

| Thành viên | Vai trò | Mảng phụ trách | Work item chính |
|---|---|---|---|
| Trịnh Thanh Tùng | Scrum Master (kiêm BE hỗ trợ) | Điều phối, theo dõi tiến độ; nhận thêm việc để kịp tiến độ | Toàn Sprint; 65, 67, 68 (BE), 62 (BE), 73, 89 (BE), 209, 210 |
| Ngô Quang Tùng | BE | OCPP – vòng đời phiên sạc | 53, 54, 55, 56, 58, 59, 94 (BE) |
| Nguyễn Lâm Tùng | BE | OCPP nâng cao, ví (quản trị) | 57, 60, 70, 74, 95 (BE) |
| Hoàng Văn Tân | BE | Biểu giá và thuật toán chia đoạn | 61, 63 (203 → 206) |
| Tạ Như Vinh | BE | Tính tiền phiên sạc | 63 (207), 64, 66 (BE), 72 |
| Hoàng Văn Đức | BE | Ví và thanh toán sandbox | 69 (BE), 71, 75 |
| Phạm Văn Tuấn | FE | Giao diện ví, thuê bao, nhật ký | 69 (FE), 70 (FE), 74 (FE), 68 (FE), 89 (FE) |
| Vy Hoàng Tú | FE | Giao diện biểu giá, hoá đơn | 61 (FE), 62 (FE), 63 (FE: 208), 66 (FE) |
| Đặng Ngọc Đại | FE | Giao diện tài xế, vận hành | 94, 95 (FE), 58 (FE), 60 (FE) |

---

## 4. Chi tiết theo từng thành viên

### Trịnh Thanh Tùng – Scrum Master
- Tổ chức Daily Scrum, Sprint Review, Sprint Retrospective.
- Theo dõi tiến độ trên Jira, cập nhật burndown, phát hiện và gỡ vướng mắc.
- Gán assignee cho các work item và subtask theo bảng phân công này.
- Điều phối lịch review chéo, đảm bảo mọi ticket có người review trước khi chuyển Done.
- Làm việc với các thành viên để làm rõ tiêu chí hoàn thành (Definition of Done).
- Thống nhất với nhóm mức ưu tiên cắt giảm (mục 6.2) vì khối lượng Sprint được dồn vào 1 tuần.

| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-65 | Bộ ca kiểm thử tính tiền có đáp án tính tay | 2 |
| SCRUM-67 | Đổi biểu giá không làm đổi tiền của phiên đã kết thúc | 2 |
| SCRUM-68 | Gói thuê bao hàng tháng với biểu giá riêng (BE) | 3 (chung) |
| SCRUM-62 | Biểu giá có nhiều khung giờ, không chồng lấn và phủ kín 24 giờ (BE) | 3 (chung) |
| SCRUM-73 | Webhook nạp ví gửi lại nhiều lần chỉ ghi nhận một, sai chữ ký bị từ chối | 3 |
| SCRUM-89 | Mọi lệnh điều khiển từ xa được ghi nhật ký kèm người thực hiện (BE) | 1 (chung) |
| SCRUM-209 | Viết test tự động cho các kịch bản phiên sạc qua nhiều khung giờ (thuộc SCRUM-63) | trong 5 (chung) |
| SCRUM-210 | [QA] Đối soát kết quả tính tiền với dữ liệu mô phỏng phiên sạc thực tế (thuộc SCRUM-63) | – |

**Gợi ý nhóm việc:**
- Bộ kiểm thử tính tiền: 65, 209, 210 dùng chung một bộ dữ liệu có đáp án tính tay. Không viết code SCRUM-203 → 207 nên đúng quy ước người kiểm thử không phải người viết code.
- Việc độc lập, làm trước: 65, 62 (kiểm tra khung giờ), 89 (làm trước hàm ghi log dùng chung), 73 (làm trên nền webhook của SCRUM-198).
- Việc chờ phụ thuộc: 67, 68 (chờ SCRUM-206 và 204 của Tân), 209 (chờ 203 → 205), 210 (chờ tính tiền và trừ ví chạy được).

**Review chéo:**
- Review SCRUM-64, 72 của Tạ Như Vinh và SCRUM-71, 75 của Hoàng Văn Đức.
- Được review: Tạ Như Vinh review SCRUM-65, 67, 68, 209; Hoàng Văn Tân review SCRUM-62, 210; Hoàng Văn Đức review SCRUM-73; Ngô Quang Tùng review SCRUM-89.

### Ngô Quang Tùng – Backend (OCPP – vòng đời phiên sạc)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-53 | Phiên sạc bắt đầu khi trụ gửi `StartTransaction` | 2 |
| SCRUM-54 | Phiên sạc kết thúc khi trụ gửi `StopTransaction` và chốt số kWh | 2 |
| SCRUM-55 | Số đo điện năng được ghi liên tục qua `MeterValues` | 2 |
| SCRUM-56 | Số đo lùi hoặc trùng mốc thời gian bị bỏ qua | 1 |
| SCRUM-58 | Vận hành viên dừng phiên sạc từ xa bằng `RemoteStopTransaction` | 2 |
| SCRUM-59 | Phiên không có tin kết thúc quá lâu bị đánh dấu bất thường | 1 |
| SCRUM-94 | API/kênh cập nhật thời gian thực cho phiên đang sạc (BE, lấy dữ liệu từ SCRUM-55) | 2 (chung) |

**Review chéo:** review SCRUM-57, 60, 95 của Nguyễn Lâm Tùng; review SCRUM-89 của Trịnh Thanh Tùng.

### Nguyễn Lâm Tùng – Backend (OCPP nâng cao, ví phía quản trị)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-57 | Phiên đang dở được khôi phục đúng khi trụ nối lại | 3 |
| SCRUM-60 | Vận hành viên đổi cấu hình trụ từ xa bằng `ChangeConfiguration` | 3 |
| SCRUM-70 | Quản trị viên nạp tay vào ví khi chưa có cổng thanh toán | 2 |
| SCRUM-74 | Tài xế xem số dư và lịch sử giao dịch ví (API) | 2 |
| SCRUM-95 | Tài xế bắt đầu phiên từ ứng dụng bằng `RemoteStartTransaction` (API) | 2 |

**Review chéo:** review SCRUM-53 → 56, 58, 59, 94 (BE) của Ngô Quang Tùng.

### Hoàng Văn Tân – Backend (Biểu giá và thuật toán chia đoạn)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-61 | Chủ trạm khai báo biểu giá theo kWh và phí chiếm trụ theo phút | 3 |
| SCRUM-63 | Phiên cắt qua nhiều khung giờ – các subtask BE: **203, 204, 205, 206** | 5 (chung) |
Subtask phụ trách trong SCRUM-63:
- SCRUM-203: Thiết kế thuật toán chia phiên sạc theo các khung giờ biểu giá
- SCRUM-204: Xây dựng hàm tính tiền theo từng đoạn thời gian trong phiên
- SCRUM-205: Xử lý trường hợp phiên cắt qua mốc đổi giá giữa đêm và giờ cao điểm
- SCRUM-206: Chuẩn hóa nguồn dữ liệu biểu giá theo thời gian áp dụng
**Review chéo:** review SCRUM-63 (207), 64, 66 (BE), 72 của Tạ Như Vinh; review SCRUM-62 và SCRUM-210 của Trịnh Thanh Tùng.

### Tạ Như Vinh – Backend (Tính tiền phiên sạc)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-63 | Subtask BE: **207** | 5 (chung) |
| SCRUM-64 | Phiên qua nửa đêm tính đúng sang biểu giá ngày hôm sau | 2 |
| SCRUM-66 | Tài xế xem hoá đơn có diễn giải từng đoạn giá (API, dữ liệu chi tiết) | 3 (chung) |
| SCRUM-72 | Ví dưới ngưỡng tối thiểu thì trụ từ chối bắt đầu phiên mới | 2 |

Subtask phụ trách trong SCRUM-63:
- SCRUM-207: Cập nhật luồng lưu trữ chi tiết các đoạn tính tiền của phiên
**Review chéo:** review SCRUM-61, 63 (203 → 206) của Hoàng Văn Tân; review SCRUM-65, 67, 68, 209 của Trịnh Thanh Tùng.

### Hoàng Văn Đức – Backend (Ví và thanh toán sandbox)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-69 | Tài xế nạp tiền vào ví qua cổng thanh toán sandbox – các subtask BE: **196, 197, 198, 199, 201** | 5 (chung) |
| SCRUM-71 | Ví bị trừ tự động khi phiên kết thúc, có bản ghi giao dịch | 3 |
| SCRUM-75 | Số dư ví luôn khớp sổ cái chỉ ghi thêm | 3 |

Subtask phụ trách trong SCRUM-69:
- SCRUM-196: Tích hợp cổng thanh toán sandbox cho chức năng nạp ví
- SCRUM-197: Thiết kế và lưu lịch sử giao dịch nạp tiền
- SCRUM-198: Xử lý callback/webhook và cập nhật số dư ví sau thanh toán
- SCRUM-199: Kiểm tra số dư ví và trừ tiền tự động khi sạc
- SCRUM-201: Xử lý các trường hợp lỗi/hoàn tiền khi nạp ví thất bại
**Review chéo:** review SCRUM-70, 74 của Nguyễn Lâm Tùng; review SCRUM-73 của Trịnh Thanh Tùng. Phần của Đức được Nguyễn Lâm Tùng và Trịnh Thanh Tùng (SCRUM-71, 75) review.

### Phạm Văn Tuấn – Frontend (Giao diện ví, thuê bao, nhật ký)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-69 | Các subtask FE: **195, 200** | 5 (chung) |
| SCRUM-70 | Màn hình quản trị nạp tay vào ví (FE) | 2 (chung) |
| SCRUM-74 | Màn hình xem số dư và lịch sử giao dịch ví (FE) | 2 (chung) |
| SCRUM-68 | Giao diện đăng ký gói thuê bao hàng tháng (FE) | 3 (chung) |
| SCRUM-89 | Màn hình xem nhật ký lệnh điều khiển từ xa (FE) | 1 (chung) |

Subtask phụ trách trong SCRUM-69:
- SCRUM-195: Thêm màn hình/luồng nạp tiền vào ví cho tài xế
- SCRUM-200: Hiển thị số dư ví và trạng thái giao dịch nạp tiền

**Test chéo:** SCRUM-202 – Test chức năng nạp tiền vào ví qua cổng thanh toán sandbox (phối hợp với Hoàng Văn Đức).

### Vy Hoàng Tú – Frontend (Giao diện biểu giá và hoá đơn)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-61 | Màn hình khai báo biểu giá theo kWh và phí chiếm trụ (FE) | 3 (chung) |
| SCRUM-62 | Màn hình cấu hình nhiều khung giờ, cảnh báo chồng lấn/thiếu giờ (FE) | 3 (chung) |
| SCRUM-63 | Subtask FE: **208** – Hiển thị chi tiết cách tính tiền theo từng khung giờ cho phiên sạc | 5 (chung) |
| SCRUM-66 | Màn hình hoá đơn có diễn giải từng đoạn giá (FE) | 3 (chung) |

> Đã chuyển SCRUM-68 (FE) sang cho **Phạm Văn Tuấn**.

### Đặng Ngọc Đại – Frontend (Giao diện tài xế và vận hành)
| Ticket | Nội dung | SP |
|---|---|---|
| SCRUM-94 | Tài xế xem phiên đang sạc của mình cập nhật theo thời gian thực (FE) | 2 (chung) |
| SCRUM-95 | Nút bắt đầu phiên sạc từ ứng dụng (FE) | 2 (chung) |
| SCRUM-58 | Nút dừng phiên sạc từ xa cho vận hành viên (FE) | 2 (chung) |
| SCRUM-60 | Form đổi cấu hình trụ từ xa (FE) | 3 (chung) |

> Đã chuyển SCRUM-89 (FE) sang cho **Phạm Văn Tuấn**.

---

## 5. Phân công theo work item (tra cứu nhanh)

| Ticket | Tên ngắn | SP | Backend | Frontend |
|---|---|---|---|---|
| SCRUM-53 | StartTransaction | 2 | Ngô Quang Tùng | – |
| SCRUM-54 | StopTransaction, chốt kWh | 2 | Ngô Quang Tùng | – |
| SCRUM-55 | MeterValues | 2 | Ngô Quang Tùng | – |
| SCRUM-56 | Bỏ qua số đo lùi/trùng | 1 | Ngô Quang Tùng | – |
| SCRUM-57 | Khôi phục phiên khi trụ nối lại | 3 | Nguyễn Lâm Tùng | – |
| SCRUM-58 | RemoteStopTransaction | 2 | Ngô Quang Tùng | Đặng Ngọc Đại |
| SCRUM-59 | Phiên bất thường | 1 | Ngô Quang Tùng | – |
| SCRUM-60 | ChangeConfiguration | 3 | Nguyễn Lâm Tùng | Đặng Ngọc Đại |
| SCRUM-61 | Khai báo biểu giá | 3 | Hoàng Văn Tân | Vy Hoàng Tú |
| SCRUM-62 | Biểu giá nhiều khung giờ | 3 | **Trịnh Thanh Tùng** | Vy Hoàng Tú |
| SCRUM-63 | Phiên cắt qua nhiều khung giờ | 5 | Tân (203–206), Vinh (207), **Trịnh Thanh Tùng** (209, 210) | Vy Hoàng Tú (208) |
| SCRUM-64 | Phiên qua nửa đêm | 2 | Tạ Như Vinh | – |
| SCRUM-65 | Bộ ca kiểm thử tính tiền | 2 | **Trịnh Thanh Tùng** | – |
| SCRUM-66 | Hoá đơn diễn giải từng đoạn | 3 | Tạ Như Vinh | Vy Hoàng Tú |
| SCRUM-67 | Đổi biểu giá không ảnh hưởng phiên cũ | 2 | **Trịnh Thanh Tùng** | – |
| SCRUM-68 | Gói thuê bao hàng tháng | 3 | **Trịnh Thanh Tùng** | Phạm Văn Tuấn |
| SCRUM-69 | Nạp ví qua cổng sandbox | 5 | Hoàng Văn Đức (196–199, 201) | Phạm Văn Tuấn (195, 200) |
| SCRUM-70 | Admin nạp tay vào ví | 2 | Nguyễn Lâm Tùng | Phạm Văn Tuấn |
| SCRUM-71 | Trừ ví khi phiên kết thúc | 3 | Hoàng Văn Đức | – |
| SCRUM-72 | Ví dưới ngưỡng thì từ chối phiên mới | 2 | Tạ Như Vinh | – |
| SCRUM-73 | Webhook idempotent, kiểm tra chữ ký | 3 | **Trịnh Thanh Tùng** | – |
| SCRUM-74 | Xem số dư và lịch sử ví | 2 | Nguyễn Lâm Tùng | Phạm Văn Tuấn |
| SCRUM-75 | Sổ cái chỉ ghi thêm | 3 | Hoàng Văn Đức | – |
| SCRUM-89 | Nhật ký lệnh điều khiển từ xa | 1 | **Trịnh Thanh Tùng** | Phạm Văn Tuấn |
| SCRUM-94 | Xem phiên sạc thời gian thực | 2 | Ngô Quang Tùng | Đặng Ngọc Đại |
| SCRUM-95 | RemoteStartTransaction từ app | 2 | Nguyễn Lâm Tùng | Đặng Ngọc Đại |

---

## 6. Phụ thuộc giữa các task (ai có thể bị ai chặn)

> Các phụ thuộc dưới đây được suy ra từ nội dung ticket, vì mục "Linked work items" trên Jira đang trống. Nên tạo liên kết "is blocked by" tương ứng để cả nhóm nhìn thấy.

### 6.1 Các điểm có thể gây nghẽn

| Task bị chặn | Người làm | Đang chờ | Người làm trước | Cách giảm chặn |
|---|---|---|---|---|
| SCRUM-57, 95 | Nguyễn Lâm Tùng | Model phiên sạc từ SCRUM-53 | Ngô Quang Tùng | Ngô chốt model `Session` và hàm dùng chung sớm; Lâm Tùng làm 60, 70, 74 trước |
| SCRUM-94 (FE) | Đặng Ngọc Đại | API dữ liệu từ SCRUM-55 | Ngô Quang Tùng | Chốt format dữ liệu realtime sớm, FE dùng dữ liệu giả trước |
| SCRUM-89 (BE) | Trịnh Thanh Tùng | Các lệnh từ xa 58, 60, 95 gọi vào hàm ghi log | Ngô Quang Tùng, Nguyễn Lâm Tùng | Trịnh Thanh Tùng làm trước một hàm ghi log dùng chung, các lệnh chỉ việc gọi vào |
| SCRUM-204, 205 | Hoàng Văn Tân | SCRUM-203, 206 (cùng người) | Hoàng Văn Tân | Làm theo thứ tự 206 → 203 → 204 → 205 |
| SCRUM-207, 64 | Tạ Như Vinh | Thuật toán chia đoạn SCRUM-203 – 205 | Hoàng Văn Tân | Tân chốt cấu trúc dữ liệu "đoạn tính tiền" và chữ ký hàm 204 sớm; Vinh code trên bản giả trước |
| SCRUM-209 | Trịnh Thanh Tùng | Thuật toán chia đoạn SCRUM-203 – 205 | Hoàng Văn Tân | Trịnh Thanh Tùng dựng sẵn bộ ca từ SCRUM-65, chạy khi Tân có bản dùng được |
| SCRUM-66 (BE) | Tạ Như Vinh | Dữ liệu đoạn tính tiền từ SCRUM-207 (cùng người) | Tạ Như Vinh | Làm 207 trước, 66 sau |
| SCRUM-67, 68 (BE) | Trịnh Thanh Tùng | Biểu giá có hiệu lực theo thời gian (206) và hàm tính tiền (204) | Hoàng Văn Tân | Trịnh Thanh Tùng bắt đầu bằng 65, 62, 89, 73 (không phụ thuộc hoặc phụ thuộc ít), 67 và 68 làm sau khi Tân xong 206 và 204 |
| SCRUM-62 (BE) | Trịnh Thanh Tùng | Cấu trúc biểu giá và khung giờ từ SCRUM-61 | Hoàng Văn Tân | Tân chốt schema biểu giá sớm để Trịnh Thanh Tùng viết hàm kiểm tra chồng lấn/phủ 24 giờ |
| SCRUM-73 | Trịnh Thanh Tùng | Handler webhook và cập nhật số dư (SCRUM-198), sổ cái (75) | Hoàng Văn Đức | Cùng một luồng webhook với 198: Đức dựng khung xử lý trước, Trịnh Thanh Tùng thêm kiểm tra chữ ký và chống ghi nhận trùng; hai bên thống nhất ranh giới ngay từ đầu |
| SCRUM-70, 74 (BE) | Nguyễn Lâm Tùng | Sổ cái và lịch sử giao dịch (75, 197) | Hoàng Văn Đức | Đức chốt schema sổ cái và hàm cộng/trừ ví sớm |
| SCRUM-195, 200, 70, 74 (FE) | Phạm Văn Tuấn | API ví (196, 198, 70, 74) | Hoàng Văn Đức, Nguyễn Lâm Tùng | Thống nhất hợp đồng API, FE dùng mock |
| SCRUM-68 (FE) | Phạm Văn Tuấn | API gói thuê bao (68 BE) | Trịnh Thanh Tùng | Trịnh Thanh Tùng chốt API sớm, Tuấn dùng mock |
| SCRUM-89 (FE) | Phạm Văn Tuấn | API nhật ký (89 BE) | Trịnh Thanh Tùng | Trịnh Thanh Tùng chốt format nhật ký sớm, Tuấn dùng mock |
| SCRUM-72 | Tạ Như Vinh | Số dư ví (Đức) và luồng bắt đầu phiên 53 (Ngô) | Hoàng Văn Đức, Ngô Quang Tùng | Đức cung cấp hàm `kiemTraSoDuToiThieu` sớm |
| SCRUM-71 | Hoàng Văn Đức | Chốt kWh (54), tính tiền (204, 207), sổ cái (75) | Ngô Quang Tùng, Tân, Vinh | Làm sau khi các phần trên có bản chạy được |
| SCRUM-208, 66 (FE) | Vy Hoàng Tú | Dữ liệu đoạn tính tiền (207, 66 BE) | Tạ Như Vinh | Chốt format hoá đơn sớm, FE dùng mock |
| SCRUM-61, 62 (FE) | Vy Hoàng Tú | API biểu giá | Hoàng Văn Tân, Trịnh Thanh Tùng (62) | Chốt API trước, FE dùng mock |
| SCRUM-58, 60, 95 (FE) | Đặng Ngọc Đại | API lệnh từ xa | Ngô Quang Tùng, Nguyễn Lâm Tùng | Chốt hợp đồng API, FE dùng mock |
| SCRUM-210 (QA), 202 (test) | Trịnh Thanh Tùng, Phạm Văn Tuấn | Toàn bộ phần tính tiền / nạp ví đã xong | Nhiều người | Làm sau cùng, chuẩn bị kịch bản từ trước |

### 6.2 Mức ưu tiên khi cần cắt giảm

Vì toàn bộ Sprint dồn vào 1 tuần, nên thống nhất sớm với Scrum Master thứ tự ưu tiên:

| Mức | Nội dung | Ticket |
|---|---|---|
| Bắt buộc | Chuỗi sạc → tính tiền → trừ ví | 53, 54, 55, 61, 62, 63, 64, 66, 71, 75 |
| Nên có | Nạp ví và điều khiển từ xa | 69, 70, 72, 73, 74, 58, 94, 95, 89 |
| Làm nếu kịp | Phần mở rộng | 56, 57, 59, 60, 65, 67, 68 |

> Riêng SCRUM-65 (bộ ca kiểm thử) nên làm sớm dù xếp mức thấp, vì 209 và 210 dùng lại bộ dữ liệu này.

### 6.3 Quy tắc chống nghẽn
- Chốt hợp đồng API và schema dữ liệu ngay đầu Sprint, ghi vào một chỗ chung.
- Người làm phần "nền" mở PR nháp sớm để người phụ thuộc có thể bám theo.
- Thêm liên kết "is blocked by" trên Jira cho các cặp task ở bảng 6.1.
- Ai bị chờ quá 1 ngày thì báo Scrum Master ngay trong Daily Scrum.

---

## 7. Kế hoạch review và kiểm thử chéo (Sprint 3)

| Người làm | Người review / test chéo |
|---|---|
| Ngô Quang Tùng | Nguyễn Lâm Tùng |
| Nguyễn Lâm Tùng | Ngô Quang Tùng (57, 60, 95), Hoàng Văn Đức (70, 74) |
| Hoàng Văn Tân | Tạ Như Vinh |
| Tạ Như Vinh | Hoàng Văn Tân (63 – 207, 66) và Trịnh Thanh Tùng (64, 72) |
| Trịnh Thanh Tùng | Tạ Như Vinh (65, 67, 68, 209), Hoàng Văn Tân (62, 210), Hoàng Văn Đức (73), Ngô Quang Tùng (89) |
| Hoàng Văn Đức | Nguyễn Lâm Tùng, Trịnh Thanh Tùng (71, 75) |
| Phạm Văn Tuấn | Vy Hoàng Tú |
| Vy Hoàng Tú | Đặng Ngọc Đại |
| Đặng Ngọc Đại | Phạm Văn Tuấn |

**Quy ước:**
- Mỗi ticket phải được ít nhất một người khác review trước khi chuyển sang Done.
- Review trong ngày khi PR được mở, không dồn đến cuối Sprint.
- Các subtask kiểm thử (SCRUM-202, SCRUM-209, SCRUM-210) do người không viết phần code tương ứng thực hiện.
- Việc tích hợp FE – BE (ví dụ SCRUM-69, SCRUM-63, SCRUM-66, SCRUM-68, SCRUM-89) cần FE và BE cùng thống nhất hợp đồng API ngay từ đầu Sprint.

---

## 8. Lưu ý

- Cột "SP (chung)" nghĩa là story point được chia cho cả BE và FE (hoặc nhiều subtask), chưa tách riêng từng phần.
- Các ticket chưa có subtask trên Jira (ví dụ SCRUM-61, 62, 66, 68, 70, 74...) nên được tách subtask `[BE]` / `[FE]` khi Sprint Planning để bám sát phân công trên.
- Các điều chỉnh so với bản trước, nhằm giảm tải và giảm phụ thuộc:
  - Ngô Quang Tùng giao SCRUM-89 (BE) cho Trịnh Thanh Tùng.
  - Hoàng Văn Tân giao SCRUM-62 (BE) cho Trịnh Thanh Tùng.
  - Tạ Như Vinh giao SCRUM-209 cho Trịnh Thanh Tùng.
  - Hoàng Văn Đức giao SCRUM-73 và SCRUM-210 cho Trịnh Thanh Tùng.
  - Vy Hoàng Tú giao SCRUM-68 (FE) cho Phạm Văn Tuấn; Đặng Ngọc Đại giao SCRUM-89 (FE) cho Phạm Văn Tuấn.
  - Đã chuyển trước đó: SCRUM-66 (BE) từ Hoàng Văn Tân sang Tạ Như Vinh; SCRUM-94 (BE) giao cho Ngô Quang Tùng.
- Nếu có người nghỉ hoặc quá tải, ưu tiên chuyển ticket cùng Epic để giữ ngữ cảnh nghiệp vụ.
