# SCRUM-205 — Phiên cắt qua nửa đêm và mốc giờ cao điểm

**Parent:** SCRUM-63 — Phiên cắt qua nhiều khung giờ.

## Phạm vi

Ghi rõ cách hàm tính giá xử lý một khoảng đo đi qua 00:00 địa phương và ranh giới giá tiếp theo trong ngày mới. Ranh giới được tìm theo múi giờ trạm; năng lượng được nội suy từ hai số đo tích lũy kề nhau nếu không có số đo tại ranh giới.

## Ca tính tay

- Múi giờ: `Asia/Ho_Chi_Minh`.
- Biểu giá lặp hằng ngày: `[00:00, 06:00)` thấp điểm `3.000 đ/kWh`; `[06:00, 17:00)` tiêu chuẩn `4.000 đ/kWh`; `[17:00, 22:00)` cao điểm `5.000 đ/kWh`; `[22:00, 24:00)` thấp điểm `3.000 đ/kWh`.
- Phiên: ngày 1 lúc 23:30 đến ngày 2 lúc 17:30.
- Chỉ số đầu/cuối: `10.000 Wh` và `28.000 Wh`; không có số đo trung gian.

Thời lượng là 18 giờ, điện năng là `18.000 Wh`. Nội suy tuyến tính tạo bốn đoạn:

| Khoảng địa phương | Thời lượng | Điện năng | Đơn giá | Thành tiền |
|---|---:|---:|---:|---:|
| Ngày 1, 23:30–24:00 | 0,5 giờ | 500 Wh | 3.000 đ/kWh | 1.500 đ |
| Ngày 2, 00:00–06:00 | 6 giờ | 6.000 Wh | 3.000 đ/kWh | 18.000 đ |
| Ngày 2, 06:00–17:00 | 11 giờ | 11.000 Wh | 4.000 đ/kWh | 44.000 đ |
| Ngày 2, 17:00–17:30 | 0,5 giờ | 500 Wh | 5.000 đ/kWh | 2.500 đ |
| **Tổng** | **18 giờ** | **18.000 Wh** |  | **66.000 đ** |

## Quy tắc biên

- Khoảng thời gian dùng dạng nửa kín `[bắt đầu, kết thúc)`: đúng 00:00 phần điện tiếp theo tra biểu giá ngày 2; đúng 06:00 phần điện tiếp theo tra khung giá mới.
- Nếu có số đo đúng tại 00:00, 06:00 hoặc 17:00, số đo đó làm mốc trực tiếp. Nếu thiếu, phân bổ theo tỷ lệ thời gian giữa hai số đo hợp lệ kề nhau.
- Phiên kết thúc đúng tại 00:00, 06:00 hoặc 17:00 không tạo đoạn 0 kWh ở phía sau ranh giới.
- Hai lần xuất hiện của khung thấp điểm thuộc hai ngày khác nhau vẫn là hai nhóm riêng trên hóa đơn.

## Ánh xạ mã nguồn

`backend/app/services/pricing.py::calculate_session_price` tạo mốc cắt theo từng ngày địa phương qua `_tariff_boundaries`, chọn giá bằng `_band_at`, rồi nhóm theo cửa sổ ngày/khung qua `_band_window`. Số tiền được làm tròn HALF_UP trên từng nhóm trước khi cộng tổng. Việc chọn phiên bản biểu giá khác nhau theo ngày thuộc phạm vi S-31.
