# SCRUM-203 — Thiết kế thuật toán chia phiên sạc theo khung giá

**Parent:** SCRUM-63 — Phiên cắt qua nhiều khung giờ.

**Phạm vi:** thiết kế phần tính tiền điện cho S-30; làm rõ đầu vào, cách cắt phiên, cách phân bổ kWh và quy tắc làm tròn. Việc chọn biểu giá khác nhau theo từng ngày thuộc S-31.

## 1. Mục tiêu và nguyên tắc

Với một phiên sạc hoàn tất, chia thời gian phiên tại mọi ranh giới đổi khung giá của trạm. Mỗi đoạn nhận đúng số kWh đã dùng trong đoạn đó và đơn giá có hiệu lực tại thời điểm đoạn diễn ra. Hóa đơn giữ các đoạn và quy tắc tính để tài xế có thể đối chiếu.

- Hàm tính giá là hàm thuần: chỉ nhận dữ liệu phiên, số đo, múi giờ và biểu giá; không truy cập cơ sở dữ liệu hay đồng hồ hệ thống.
- Thời điểm OCPP được chuẩn hóa về UTC để sắp xếp và tính khoảng thời gian. Khung giá được tra theo giờ địa phương của trạm.
- Số đo công-tơ là năng lượng tích lũy Wh. Không dùng số thực nhị phân cho tiền; kết quả tiền lưu bằng số nguyên đồng.
- Không suy đoán dữ liệu thiếu ngoài nội suy tuyến tính giữa hai số đo hợp lệ kề nhau.

## 2. Hợp đồng dữ liệu

### Đầu vào

| Trường | Ý nghĩa / điều kiện |
|---|---|
| `started_at`, `ended_at` | Thời điểm bắt đầu/kết thúc; kết thúc không trước bắt đầu. |
| `meter_start_wh`, `meter_stop_wh` | Chỉ số tích lũy đầu/cuối, theo Wh; chỉ số cuối không nhỏ hơn đầu. |
| `meter_readings` | Các số đo giữa phiên, có thời điểm, giá trị và đơn vị Wh hoặc kWh; chỉ nhận `Energy.Active.Import.Register`. |
| `bands` | Các khung trong ngày dạng `[start_minute, end_minute)`, kèm nhãn và giá VND/kWh. Danh sách phải phủ kín 00:00–24:00, không chồng lấn, không có giá âm. |
| `timezone_name` | Tên IANA của múi giờ trạm, ví dụ `Asia/Ho_Chi_Minh`. |

### Đầu ra

`total_vnd`, danh sách `segments` theo thứ tự thời gian, và `rounding_rule`. Mỗi đoạn điện gồm thời điểm đầu/cuối tại múi giờ trạm, nhãn khung, kWh, đơn giá và thành tiền. Hóa đơn lưu bản chụp các đoạn cùng phiên bản thuật toán để không bị thay đổi khi biểu giá được cập nhật về sau.

## 3. Các bước tính

1. **Kiểm tra dữ liệu:** xác thực dải khung giá phủ đủ 1.440 phút; kiểm tra mốc thời gian, chỉ số công-tơ, đơn vị và múi giờ. Dữ liệu không hợp lệ trả lỗi miền, không phát hành hóa đơn sai.
2. **Chuẩn hóa số đo:** tạo chuỗi `(thời điểm UTC, Wh)` từ số đầu, các số đo giữa phiên hợp lệ, và số cuối. Bỏ số đo ngoài khoảng phiên, sai measurand/đơn vị, giá trị không hữu hạn hoặc nằm ngoài hai chỉ số đầu-cuối. Sắp xếp theo thời điểm; nếu trùng thời điểm, giữ chỉ số tích lũy cao nhất. Loại số đo lùi; chuỗi phải kết thúc đúng tại số đo cuối.
3. **Tạo các khoảng đo:** với từng cặp số đo hợp lệ liên tiếp `(t0, e0)` và `(t1, e1)`, năng lượng trong khoảng là `e1 - e0` Wh. Nếu chênh lệch thời gian bằng 0 thì không tạo năng lượng cho khoảng đó.
4. **Cắt tại ranh giới giá:** lấy hợp các mốc đầu/cuối khung giá trong từng ngày địa phương mà khoảng đo đi qua. Cắt khoảng đo tại mọi mốc nằm bên trong nó. Tính cả mốc 00:00 khi phiên qua ngày mới; mốc kết thúc 24:00 tương đương 00:00 ngày kế tiếp.
5. **Phân bổ kWh:** nếu hai số đo kề nhau cách nhau `D` giây, đoạn con kéo dài `d` giây nhận `ΔWh × d / D`. Đây là nội suy tuyến tính theo thời gian giữa hai số đo; số đo đúng ranh giới được dùng trực tiếp, không cần nội suy qua ranh giới đó. Giữ độ chính xác thập phân trong suốt bước này.
6. **Gom và tính tiền:** gom các đoạn con thuộc cùng một lần xuất hiện của khung giá địa phương (cùng ngày, cùng giờ bắt đầu/kết thúc, cùng nhãn và đơn giá). Tính thành tiền từng khung: `round_half_up(kWh × VND/kWh)` đến đồng. Tổng hóa đơn bằng tổng thành tiền đã làm tròn của từng khung; không tính lại bằng cách làm tròn tổng phiên.
7. **Lưu giải trình:** ghi các đoạn theo thời gian, tổng tiền, quy tắc làm tròn và phiên bản thuật toán vào hóa đơn bất biến.

## 4. Pseudocode

```text
validate(session, bands, timezone)
points = normalize_and_validate_meter_readings(session, readings)
energy_segments = []

for (t0, e0), (t1, e1) in adjacent_pairs(points):
    if t1 == t0:
        continue
    cuts = [t0] + local_tariff_boundaries_between(t0, t1, timezone, bands) + [t1]
    for (a, b) in adjacent_pairs(cuts):
        band = band_at(local_time(a, timezone), bands)
        energy_wh = (e1 - e0) * seconds(a, b) / seconds(t0, t1)
        append_or_accumulate(energy_segments, local_window(a, band), energy_wh)

for segment in energy_segments:
    segment.amount_vnd = HALF_UP(segment.energy_wh * segment.price_vnd_per_kwh / 1000)

return sum(segment.amount_vnd), energy_segments, rounding_rule
```

## 5. Bất biến cần giữ

- Các khoảng con tạo thành một phân hoạch liên tục của phiên: đoạn đầu bắt đầu tại `started_at`, đoạn cuối kết thúc tại `ended_at`; không có khoảng trống hoặc chồng lấn.
- Mỗi thời điểm thuộc đúng một khung giá nhờ quy ước nửa kín `[bắt đầu, kết thúc)`. Ranh giới được cắt một lần và phần sau ranh giới tra khung mới.
- Trước khi làm tròn tiền, tổng năng lượng phân bổ qua các đoạn bằng `meter_stop_wh - meter_start_wh`. Việc định dạng kWh để hiển thị không tham gia tính tiền.
- Mỗi nhóm tiền được khóa theo lần xuất hiện của khung trong ngày địa phương, gồm ngày, giờ bắt đầu/kết thúc, nhãn và đơn giá. Không gộp hai ngày thành một dòng dù nhãn và giá giống nhau.
- Một phiên có thời lượng bằng 0 tạo danh sách đoạn điện rỗng và tiền điện bằng 0. Phí chiếm trụ, nếu có, vẫn là một dòng riêng theo quy tắc của biểu giá.

## 6. Quy tắc biên và ví dụ

- Khung giờ dùng đoạn nửa kín `[bắt đầu, kết thúc)`: đúng thời điểm đổi giá thì năng lượng tiếp theo thuộc khung mới; không tính hai lần tại ranh giới.
- Phiên nằm trọn trong một khung tạo một đoạn tính tiền. Phiên kết thúc đúng ranh giới không tạo đoạn 0 kWh ở khung kế tiếp.
- Số đo bắt đầu `1000 Wh` lúc 21:30, kết thúc `3000 Wh` lúc 23:30; giá đổi lúc 22:00. Nội suy tuyến tính cho `[21:30, 22:00)` là `500 Wh`, `[22:00, 23:30]` là `1500 Wh`. Mỗi phần nhân với đơn giá tương ứng.
- Làm tròn theo từng đoạn có thể khác làm tròn một lần trên tổng: hai lần xuất hiện khung, mỗi lần `0,1 kWh × 2.005 đồng/kWh = 200,5 đồng`, mỗi đoạn làm tròn HALF_UP thành `201 đồng`, tổng hóa đơn là `402 đồng`. Làm tròn một lần trên `401 đồng` sẽ sai quy tắc.
- Phiên qua nửa đêm phải cắt tại 00:00 địa phương. Biểu giá và việc nhóm dòng theo ngày được chọn theo ngày địa phương; xử lý biểu giá phiên bản khác nhau giữa hai ngày thuộc S-31.
- Số đo lùi không được làm âm lượng điện. Bỏ số đo lùi; nếu không còn chuỗi hợp lệ tới đúng số đo cuối thì từ chối tính hóa đơn.
- Không có số điện tiêu thụ vẫn có thể trả về tổng tiền điện bằng 0 và danh sách đoạn điện rỗng; phí chiếm trụ (nếu bật) là dòng phí riêng, không gộp vào kWh.
- Phiên có thời lượng bằng 0 nhưng chỉ số công-tơ đầu/cuối khác nhau là dữ liệu không nhất quán và phải bị từ chối.

## 7. Độ phức tạp và ánh xạ triển khai

Với `n` số đo, sắp xếp tốn `O(n log n)`. Gọi `M` là tổng số mốc lịch được xét qua tất cả các khoảng đo và `m` là số đoạn giá kết quả; quét/cắt tốn `O(n + M)`, còn sắp xếp kết quả tốn tối đa `O(m log m)`. Số khung trong ngày thường nhỏ nên không cần tối ưu hóa trước.

Trong code hiện tại, phần thuần nằm ở `backend/app/services/pricing.py::calculate_session_price`; nó kiểm tra dải giờ, chuẩn hóa số đo, tìm mốc giờ địa phương, nội suy và làm tròn theo từng khung. `backend/app/services/billing.py::finalize_session_billing` lấy biểu giá, gọi hàm thuần và lưu snapshot hóa đơn. Việc truy vấn chọn biểu giá hiệu lực theo từng ngày và nhóm hóa đơn theo ngày cần được hoàn thiện/đánh giá ở S-31; hàm hiện nhận một bộ `bands` cho toàn phiên nên chưa tự tra nhiều phiên bản biểu giá trong cùng một phiên.

## 8. Điểm kiểm chứng nghiệm thu

- Một khung; đổi khung có số đo đúng ranh giới; đổi khung phải nội suy; kết thúc đúng ranh giới.
- Qua nửa đêm; qua nhiều ngày; biên ngày địa phương.
- Số đo trùng thời điểm, lùi, sai đơn vị, ngoài phiên, không tăng tới chỉ số cuối.
- Phủ thiếu giờ, chồng khung, khung kết thúc ở 24:00, giá bằng 0.
- Ca làm tròn khiến tổng theo từng khung khác làm tròn toàn phiên; hóa đơn phải theo tổng các khung đã làm tròn.
