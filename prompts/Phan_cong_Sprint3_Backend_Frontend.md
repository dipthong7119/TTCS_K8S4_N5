# Phân công lại Sprint 3 (chỉ Backend / Frontend, không có Tester)

> Tổng: **60 SP**, **23 task chính**, **9 thành viên**. Tải trung bình ≈ **6,7 SP/người**.
> Mục tiêu: **không trùng việc**, **không chờ nhau**, tải mỗi người đều (5–8 SP).

---

## 1. Giả định cần bạn xác nhận

| # | Giả định                                                                                                                                       | Nếu khác thì sao                                                                         |
| - | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 1 | **Tạ Như Vinh** và **Hoàng Văn Đức** (trước là Tester) chuyển sang **Backend**, tự viết test cho phần mình làm. | Đổi vai trò thì chỉ cần hoán đổi người ở bảng mục 3, logic chia không đổi. |
| 2 | **Trịnh Thanh Tùng** (Scrum Master) giữ T-55, T-56 và 1 phần T-46. Tải nhẹ hơn (5 SP) vì còn điều phối.                        | Có thể chuyển bớt cho Vy Hoàng Tú.                                                    |
| 3 | Jira chưa có SP cho subtask, nên SP subtask ở dưới là**ước lượng tạm** (tổng khớp SP task cha).                               | Nên poker lại nhanh 10 phút đầu sprint.                                                |
| 4 | Sprint ≈**10 ngày làm việc**. Cột "Ngày" ở mục 6 chỉ là gợi ý.                                                                  | Co giãn theo độ dài sprint thật.                                                       |

---

## 2. Nguyên tắc chia (vì sao ít chờ, ít trùng)

1. **Chia theo lát dọc (vertical slice)**: mỗi người làm trọn một mảng, không nhiều người cùng sửa một handler.
   - Vòng đời phiên → Quang Tùng
   - Số đo (MeterValues) → Lâm Tùng
   - Tính kWh + API phiên hiện tại + audit → Tân
   - Mất kết nối / phiên bất thường → Vinh
   - Điều khiển từ xa (bắt đầu/dừng) → Đức (BE) + Đại, Tuấn (FE)
2. **Task nền tảng đặt đầu sprint**: T-36 (bảng phiên), T-40 (bảng số đo), T-57 (audit), T-55 (docker trụ ảo) làm xong sớm vì nhiều người cần.
3. **Việc không phụ thuộc ai** được xếp ngay đầu sprint cho người đang chờ (ví dụ hàm tính kWh thuần của Tân, dữ liệu mẫu của Vinh, mock API cho FE).
4. **FE làm bằng mock API** từ ngày 1 theo hợp đồng API chốt chung, tới khi BE xong thì đổi sang API thật.
5. **Người rảnh sớm nhận việc cuối sprint** (kịch bản 20 trụ, bảng đối chiếu, bằng chứng kiểm thử) thay vì ngồi chờ.

---

## 3. Phân công mới theo người

| Thành viên                 | Vai trò     | Công việc                                                                           | SP           |
| ---------------------------- | ------------ | ------------------------------------------------------------------------------------- | ------------ |
| **Trịnh Thanh Tùng** | Scrum Master | T-55, T-56, SCRUM-185 (đóng gói kịch bản vào CI)                                | **5**  |
| **Ngô Quang Tùng**   | Backend      | T-36, T-37, T-38, SCRUM-189 (tích hợp kWh vào luồng phiên)                       | **8**  |
| **Nguyễn Lâm Tùng** | Backend      | T-40, T-41, T-42, T-44                                                                | **8**  |
| **Hoàng Văn Tân**   | Backend      | SCRUM-187 (hàm tính kWh), T-47, T-57                                                | **7**  |
| **Tạ Như Vinh**      | Backend      | SCRUM-188 (dữ liệu 3 phiên mẫu), T-43, T-45, T-53                                 | **7**  |
| **Hoàng Văn Đức**  | Backend      | T-51, T-49, SCRUM-193 (tích hợp API bắt đầu sạc), SCRUM-183 (đối chiếu kWh)  | **7**  |
| **Phạm Văn Tuấn**   | Frontend     | T-48, T-50, SCRUM-184 (xuất bảng đối chiếu), SCRUM-186 (bằng chứng kiểm thử) | **6**  |
| **Vy Hoàng Tú**      | Frontend     | T-54, T-58, SCRUM-182 (thiết kế kịch bản 20 trụ)                                 | **5**  |
| **Đặng Ngọc Đại** | Frontend     | SCRUM-190, 191, 192, 194 (thuộc T-52)                                                | **7**  |
| **Tổng**              |              |                                                                                       | **60** |

Theo nhóm: Backend 37 SP (5 người) · Frontend 18 SP (3 người) · Scrum Master 5 SP.

---

## 4. Chi tiết từng task (23 task chính)

"Review" là người duyệt code/PR, chọn khác người làm và khác lát việc để có thêm một góc nhìn.

| Mã Jira     | Mã Excel | Tiêu đề                                                                 | SP | Người làm                      | Review        | Thay đổi so với cũ                                                              |
| ------------ | --------- | -------------------------------------------------------------------------- | -- | --------------------------------- | ------------- | ----------------------------------------------------------------------------------- |
| SCRUM-115    | T-55      | Dịch vụ trụ ảo trong`docker-compose`, số lượng cấu hình được | 2  | Trịnh Thanh Tùng                | Đức         | Giữ nguyên                                                                        |
| SCRUM-116    | T-56      | Bước CI chạy kịch bản 20 trụ ảo, chặn merge khi thất bại         | 2  | Trịnh Thanh Tùng                | Đức         | Giữ nguyên                                                                        |
| SCRUM-161    | T-36      | Bảng`charging_sessions` + migration                                     | 2  | Ngô Quang Tùng                  | Lâm Tùng    | Giữ nguyên                                                                        |
| SCRUM-162    | T-37      | Handler`StartTransaction`                                                | 2  | Ngô Quang Tùng                  | Lâm Tùng    | Giữ nguyên                                                                        |
| SCRUM-163    | T-38      | Handler`StopTransaction`                                                 | 2  | Ngô Quang Tùng                  | Lâm Tùng    | Giữ nguyên                                                                        |
| SCRUM-164    | T-39      | Tính kWh bằng hiệu số đo, test 3 phiên mẫu                          | 8  | Tân + Vinh + Quang Tùng         | Xem dòng con | Giữ nguyên người,**chia lại SP subtask**                                 |
| ↳ SCRUM-187 |           | Hàm thuần tính kWh từ hai số đo Wh + unit test                       | 4  | Hoàng Văn Tân                  | Vinh          | Giữ nguyên                                                                        |
| ↳ SCRUM-188 |           | Dữ liệu 3 phiên mẫu tính tay                                          | 2  | Tạ Như Vinh                     | Tân          | Giữ nguyên                                                                        |
| ↳ SCRUM-189 |           | Tích hợp hàm kWh vào luồng`StopTransaction`                         | 2  | Ngô Quang Tùng                  | Lâm Tùng    | Giữ nguyên                                                                        |
| SCRUM-165    | T-40      | Bảng`meter_values` + migration + chỉ mục                              | 2  | Nguyễn Lâm Tùng                | Quang Tùng   | Giữ nguyên                                                                        |
| SCRUM-166    | T-41      | Handler`MeterValues`                                                     | 2  | Nguyễn Lâm Tùng                | Quang Tùng   | Giữ nguyên                                                                        |
| SCRUM-167    | T-42      | So mốc thời gian với số đo mới nhất                                 | 1  | Nguyễn Lâm Tùng                | Quang Tùng   | Giữ nguyên                                                                        |
| SCRUM-168    | T-43      | Test số đo lùi / trùng, cảnh báo trong log                           | 1  | Tạ Như Vinh                     | Tân          | Giữ nguyên người, đổi vai trò Tester → Backend                              |
| SCRUM-169    | T-44      | Khớp phiên đang chạy theo`transactionId` khi trụ nối lại          | 3  | Nguyễn Lâm Tùng                | Quang Tùng   | Giữ nguyên                                                                        |
| SCRUM-170    | T-45      | Xử lý`StopTransaction` tới muộn sau khi trụ ngoại tuyến           | 3  | **Tạ Như Vinh**           | Lâm Tùng    | **Đổi** từ Lâm Tùng (giảm tải, gom nhóm "mất kết nối" cùng T-53)  |
| SCRUM-171    | T-46      | Kịch bản 20 trụ ảo ngắt–nối ngẫu nhiên, kiểm kWh cuối           | 8  | Tú + Đức + Tuấn + Thanh Tùng | Xem dòng con | **Chia lại cho 4 người** (trước đó Đức làm 4 subtask)               |
| ↳ SCRUM-182 |           | Thiết kế kịch bản tự động 20 trụ                                   | 3  | Vy Hoàng Tú                     | Đức         | **Đổi** từ Đức                                                           |
| ↳ SCRUM-183 |           | Thu thập và đối chiếu kWh hệ thống vs simulator                     | 2  | Hoàng Văn Đức                 | Tân          | Giữ nguyên                                                                        |
| ↳ SCRUM-184 |           | Xuất bảng đối chiếu kết quả                                         | 1  | Phạm Văn Tuấn                  | Tú           | **Đổi** từ Đức                                                           |
| ↳ SCRUM-185 |           | Đóng gói kịch bản để chạy trong CI                                 | 1  | Trịnh Thanh Tùng                | Đức         | Giữ nguyên                                                                        |
| ↳ SCRUM-186 |           | Bằng chứng kiểm thử cho AC của S-21 và E-04                          | 1  | Phạm Văn Tuấn                  | Tú           | **Đổi** từ Đức                                                           |
| SCRUM-172    | T-49      | Gửi`RemoteStopTransaction`, chờ trụ gửi `StopTransaction` thật    | 2  | **Hoàng Văn Đức**       | Quang Tùng   | **Đổi** từ Quang Tùng                                                     |
| SCRUM-173    | T-50      | Nút dừng trên màn hình phiên                                         | 2  | Phạm Văn Tuấn                  | Đại         | Giữ nguyên                                                                        |
| SCRUM-174    | T-53      | Job quét phiên đang chạy mà trụ ngoại tuyến quá ngưỡng          | 1  | **Tạ Như Vinh**           | Tân          | **Đổi** từ Tân                                                            |
| SCRUM-175    | T-54      | Danh sách phiên bất thường trên màn hình vận hành                | 1  | Vy Hoàng Tú                     | Tuấn         | Giữ nguyên                                                                        |
| SCRUM-176    | T-57      | Bảng`audit_logs` + hàm ghi dùng chung                                 | 1  | Hoàng Văn Tân                  | Vinh          | Giữ nguyên                                                                        |
| SCRUM-177    | T-58      | Màn hình tra nhật ký                                                   | 1  | Vy Hoàng Tú                     | Tuấn         | Giữ nguyên                                                                        |
| SCRUM-178    | T-47      | API phiên hiện tại của tài xế, kèm kWh mới nhất                   | 2  | Hoàng Văn Tân                  | Vinh          | Giữ nguyên                                                                        |
| SCRUM-179    | T-48      | Màn hình phiên đang sạc, kWh tăng dần không cần tải lại         | 2  | Phạm Văn Tuấn                  | Đại         | Giữ nguyên                                                                        |
| SCRUM-180    | T-51      | API bắt đầu phiên, gửi`RemoteStartTransaction`                      | 2  | **Hoàng Văn Đức**       | Quang Tùng   | **Đổi** từ Quang Tùng                                                     |
| SCRUM-181    | T-52      | Nút bắt đầu sạc trên màn hình trụ                                 | 8  | Đại + Đức                     | Tuấn         | Giữ nguyên Đại,**chuyển subtask BE/test**                                |
| ↳ SCRUM-190 |           | [FE] Nút bắt đầu sạc + danh sách đầu nối                          | 3  | Đặng Ngọc Đại                | Tuấn         | Giữ nguyên                                                                        |
| ↳ SCRUM-191 |           | [FE] Trạng thái chờ tối đa 60 giây                                   | 2  | Đặng Ngọc Đại                | Tuấn         | Giữ nguyên                                                                        |
| ↳ SCRUM-192 |           | [FE] 3 thông báo: từ chối, trụ bận, hết thời gian                  | 1  | Đặng Ngọc Đại                | Tuấn         | Giữ nguyên                                                                        |
| ↳ SCRUM-193 |           | [BE] Tích hợp API bắt đầu sạc, map phản hồi từ trụ               | 1  | **Hoàng Văn Đức**       | Quang Tùng   | **Đổi** từ Quang Tùng (cùng người làm T-51 nên không phải chờ ai) |
| ↳ SCRUM-194 |           | Test tính năng bắt đầu sạc trên màn hình chi tiết trụ           | 1  | **Đặng Ngọc Đại**      | Tuấn         | **Đổi** từ Vinh (không còn Tester)                                       |

---

## 5. Lý do các thay đổi chính

| Thay đổi                                                 | Lý do                                                                                                                                                                                                     |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-49, T-51, SCRUM-193 chuyển từ Quang Tùng sang Đức   | Quang Tùng đang giữ đường găng (T-36 → T-37 → T-38). Cũ: 10 SP + 2 subtask = trên 13 SP. Mới: 8 SP. Điều khiển từ xa thành một mảng riêng, Đức làm trọn cả bắt đầu lẫn dừng. |
| T-45, T-53 chuyển sang Vinh                               | Cùng chủ đề "mất kết nối / phiên bất thường", Vinh làm trọn mảng này. Lâm Tùng giảm từ 11 SP xuống 8, Tân giảm từ 12 SP xuống 7.                                                   |
| T-46 chia 4 người                                        | Cũ: Đức gánh một mình 8 SP và là mắt xích cuối. Mới: các phần độc lập chạy song song (thiết kế kịch bản, đối chiếu, xuất bảng, đóng gói CI).                                 |
| Tú, Tuấn nhận phần việc kịch bản/bảng đối chiếu | Việc FE của hai bạn ít (tổng 14 SP FE cho 3 người). Nhận thêm các việc dạng script/test để tải đều.                                                                                       |
| SCRUM-194 chuyển cho Đại                                | Người làm tính năng tự test đường chạy đầy đủ, Tuấn review.                                                                                                                                 |

---

## 6. Phụ thuộc và cách tránh chờ

| Ai cần                                | Chờ gì                             | Từ ai                  | Cách tránh chờ                                                                                                                        |
| -------------------------------------- | ------------------------------------ | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Quang Tùng (T-37, T-38)               | Bảng phiên                         | Quang Tùng (T-36)      | Cùng một người, làm T-36 trước và**merge migration ngay ngày 1–2**.                                                      |
| Lâm Tùng (T-41)                      | Bảng số đo                        | Lâm Tùng (T-40)       | Cùng một người. Migration dùng timestamp riêng, không trùng số thứ tự với T-36.                                              |
| Quang Tùng (SCRUM-189)                | Hàm kWh                             | Tân (SCRUM-187)        | Tân làm 187 từ ngày 1 (hàm thuần, không phụ thuộc ai), xong trước khi Quang Tùng cần.                                       |
| Tân (SCRUM-187)                       | Dữ liệu mẫu để test             | Vinh (SCRUM-188)        | Vinh làm 188**đầu tiên** (ngày 1–2). Tân viết hàm trước, gắn test khi có dữ liệu.                                   |
| Đức (T-49, T-51)                     | Bảng phiên và handler             | Quang Tùng             | T-51 không cần bảng phiên nên làm trước. T-49 xếp sau, khi T-36/T-37 đã merge.                                                |
| Tân (T-47)                            | Bảng phiên và số đo             | Quang Tùng, Lâm Tùng | Xếp T-47 vào giữa sprint, lúc hai bảng đã có.                                                                                    |
| Vinh (T-45)                            | `StopTransaction` và khớp phiên | Quang Tùng, Lâm Tùng | Xếp T-45 sau T-38 và T-44. Review chéo với Lâm Tùng.                                                                               |
| Tuấn (T-48), Đại, Tú, Tuấn (T-50) | API thật                            | Tân, Đức, Vinh, Tân | **Mock API ngay ngày 1** theo hợp đồng chốt chung, đổi sang API thật khi BE xong.                                          |
| Tú (T-58)                             | `audit_logs`                       | Tân (T-57)             | Tân làm T-57**trước tiên trong ngày 1**. Tú làm T-58 sau.                                                                  |
| Tú (SCRUM-182)                        | Docker trụ ảo                      | Thanh Tùng (T-55)      | T-55 làm ngày 1–2. Tú chỉ bắt đầu 182 sau khi T-55 xong.                                                                         |
| Đức (SCRUM-183)                      | Kết quả chạy kịch bản           | Tú (SCRUM-182)         | Chốt**định dạng dữ liệu (JSON)** ngay đầu sprint. Đức viết công cụ đối chiếu bằng dữ liệu giả trong lúc chờ. |
| Tuấn (184, 186)                       | Dữ liệu đối chiếu               | Đức                   | Tuấn viết khung bảng bằng dữ liệu giả; việc cuối sprint nên không chặn ai.                                                   |
| Thanh Tùng (T-56, 185)                | Kịch bản 20 trụ                   | Tú (182)               | T-56 dựng khung CI trước với kịch bản nhỏ (3 trụ), khi 182 xong chỉ cần thay kịch bản.                                       |

---

## 7. Lịch gợi ý (giả định 10 ngày làm việc)

| Người               | N1                | N2          | N3              | N4         | N5   | N6                   | N7                   | N8                 | N9                    | N10    |
| --------------------- | ----------------- | ----------- | --------------- | ---------- | ---- | -------------------- | -------------------- | ------------------ | --------------------- | ------ |
| **Thanh Tùng** | T-55              | T-55        | T-56 (khung CI) | T-56       | T-56 | Hỗ trợ gỡ vướng |                      | 185                | 185                   | Buffer |
| **Quang Tùng** | T-36 (merge sớm) | T-36 / T-37 | T-37            | T-38       | T-38 | 189                  | 189                  | Review / sửa lỗi |                       |        |
| **Lâm Tùng**  | T-40              | T-40 / T-41 | T-41            | T-42       | T-44 | T-44                 | T-44                 | T-44               | Sửa lỗi             |        |
| **Tân**        | T-57 → 187       | 187         | 187             | 187        | T-47 | T-47                 | T-47                 | Review / buffer    |                       |        |
| **Vinh**        | 188               | 188         | T-53            | T-43       | T-43 | T-45                 | T-45                 | T-45               | T-45                  | Buffer |
| **Đức**       | T-51              | T-51        | T-51 / 193      | 193 / T-49 | T-49 | T-49                 | 183 (dữ liệu giả) | 183                | 183 (dữ liệu thật) |        |
| **Tuấn**       | T-48 (mock)       | T-48        | T-50 (mock)     | T-50       | T-50 | Nối API thật       | Nối API thật       | 184                | 186                   | 186    |
| **Tú**         | T-58              | T-58        | T-54 (mock)     | 182        | 182  | 182                  | 182                  | 182                | Hỗ trợ bằng chứng |        |
| **Đại**       | 190               | 190         | 190             | 191        | 191  | 192                  | 194 (API thật)      | 194                | Buffer / hỗ trợ     |        |

agyBuffer cuối sprint dùng để sửa lỗi phát sinh khi chạy kịch bản 20 trụ và hoàn thiện bằng chứng.

---

## 8. Quy tắc phối hợp

1. **Họp chốt hợp đồng ngày 1 (30–45 phút)**, cả team tham dự, chốt:
   - Schema `charging_sessions`, `meter_values`, `audit_logs`.
   - Hình dạng response/lỗi của các API: T-47, T-51, T-49, T-53, T-57.
   - Cách FE nhận kWh tăng dần (WebSocket hoặc SSE hoặc polling).
   - Định dạng JSON kết quả đối chiếu cho SCRUM-183/184.
2. **Mỗi file/handler có một chủ**: `StartTransaction`/`StopTransaction` chỉ Quang Tùng sửa; `MeterValues` chỉ Lâm Tùng sửa; hàm ghi audit chỉ Tân sửa. Người khác cần thay đổi thì nhờ chủ file hoặc tạo PR nhỏ cho chủ file duyệt.
3. **Merge sớm, merge nhỏ**: ưu tiên merge T-36, T-40, T-57, T-55 trong 2 ngày đầu để các việc sau bám vào.
4. **Review trong ngày**: người được chỉ định review trả lời trong vòng nửa ngày làm việc, tránh PR nằm chờ.
5. **Họp đầu ngày 10 phút**: mỗi người nói đang làm gì, ai đang chờ ai. Việc bị chặn quá nửa ngày thì báo Scrum Master để đổi người hỗ trợ.
6. **Ai xong sớm thì hỗ trợ**: người xong việc nên nhận review hoặc phụ việc cho người có tải nặng cuối sprint (Vinh với T-45, Đức với 183, Tuấn với 186).

---

## 9. Rủi ro cần theo dõi

| Rủi ro                                                                                | Cách giảm                                                                                                      |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Vinh và Đức trước đây là Tester, nhận việc BE có thể chậm hơn dự kiến. | Ghép review với người cùng mảng (Lâm Tùng với T-45, Quang Tùng với T-49/T-51). Có buffer ở N9–N10. |
| Quang Tùng là đường găng của cả sprint (T-36 → T-37 → T-38 → 189).          | Chỉ giữ việc lõi, ưu tiên cho T-36 trước; Lâm Tùng review nhanh.                                       |
| T-46 (20 trụ ngắt–nối ngẫu nhiên) dễ lộ lỗi muộn.                            | Chạy thử bản nhỏ (3 trụ) trên CI từ giữa sprint, tăng dần lên 20 trụ.                                |
| SP subtask ước lượng, có thể lệch.                                              | Poker lại đầu sprint; điều chỉnh nhưng giữ tổng SP task cha.                                            |
