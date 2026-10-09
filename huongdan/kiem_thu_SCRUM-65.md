# SCRUM-65 / S-32 — Bộ ca kiểm thử tính tiền có đáp án tính tay

**Người phụ trách và lập đáp án:** Trịnh Thanh Tùng (cùng Codex).

**Ngày lập:** 09/10/2026, UTC+7. **Story point:** 2.

**Người review theo phân công:** Tạ Như Vinh — chưa review.

Phạm vi lấy từ [phân công Sprint 3, 4, 5](phan-cong-sprint-345.md) và
[S-32 trong đặc tả](../prompts/02_DAC_TA_DU_AN.md): ít nhất 12 ca, gồm một khung,
cắt ranh giới, qua nửa đêm, phí chiếm trụ và số đo thưa. Khi sai phải chỉ ra
mã ca, đoạn sai và số tiền chênh lệch.

## 1. Dữ liệu và quy ước

- Đáp án độc lập: [scrum65_pricing_cases.json](../backend/tests/scrum65_pricing_cases.json).
- Test: [test_scrum65_pricing.py](../backend/tests/unit/test_scrum65_pricing.py).
- Hàm thực tế được kiểm tra: `app.services.pricing.calculate_session_price`.
- Dữ liệu đầu vào và đáp án được ghi trực tiếp trong JSON, có phép tính giải thích;
  test chỉ đọc đáp án, không gọi thuật toán để sinh lại đáp án.
- Múi giờ trạm là `Asia/Ho_Chi_Minh` (UTC+7). Số đo đầu/cuối là Wh tích lũy;
  số đo giữa phiên ghi rõ `Wh` hoặc `kWh`.
- Biểu giá mẫu độc lập trong JSON: 00:00–06:00: 3.000 đồng/kWh;
  06:00–17:00: 4.000; 17:00–22:00: 5.000; 22:00–24:00: 3.000.
  Các giá 499, 500, 3.333 đồng/kWh chỉ dùng cho ca kiểm tra làm tròn.
- Theo S-30 và hàm hiện tại: gộp số đo trong cùng đoạn khung giá của cùng ngày,
  làm tròn tiền mỗi đoạn tới đồng bằng `ROUND_HALF_UP`, rồi cộng. Ví dụ 0,5 → 1;
  1,5 → 2; 0,499 → 0. Test không triển khai thêm hàm làm tròn nghiệp vụ.
- Các khoảng thời gian tính phí chiếm trụ đều là số phút nguyên. Chưa đặt thêm
  quy tắc cho phút lẻ vì không thuộc phần đã được đặc tả.

## 2. Bảng đối chiếu tính tay

Giá trị dưới đây là đồng. Số Wh chi tiết, mốc số đo, điện năng và đơn giá từng
đoạn nằm trong JSON. `01` trong bảng tương ứng ID đầy đủ `SCRUM65-01`.

| Ca | Kịch bản | Phép tính độc lập | Tổng | Trạng thái local |
| --- | --- | --- | ---: | --- |
| 01 | 01:00–02:00, một khung thấp điểm | 2 × 3.000 | 6.000 | Đạt |
| 02 | 09:00–10:00, kWh có phần lẻ | 3,75 × 4.000 | 15.000 | Đạt |
| 03 | 18:00–19:00, một khung cao điểm | 2 × 5.000 | 10.000 | Đạt |
| 04 | 21:30–23:30, có số đo đúng 22:00 | 3 × 5.000 + 5 × 3.000 | 30.000 | Đạt |
| 05 | Cùng giờ ca 04 nhưng chỉ có số đo đầu/cuối | 8 × 30/120 = 2 kWh trước mốc; 2 × 5.000 + 6 × 3.000 | 28.000 | Đạt |
| 06 | Kết thúc đúng 22:00 | 2 × 5.000; chỉ một đoạn | 10.000 | Đạt |
| 07 | Bắt đầu đúng 22:00 | 2 × 3.000; chỉ một đoạn | 6.000 | Đạt |
| 08 | Cắt 06:00, có số đo tại mốc | 1 × 3.000 + 3 × 4.000 | 15.000 | Đạt |
| 09 | Cắt 17:00, nội suy | 2 × 4.000 + 2 × 5.000 | 18.000 | Đạt |
| 10 | 23:00–01:00, cùng biểu giá qua hai ngày | 4 × 3.000 + 4 × 3.000; hai đoạn | 24.000 | Đạt |
| 11 | 16:00Z–18:00Z, tương ứng 23:00–01:00 tại trạm | 4 × 3.000 + 4 × 3.000; chia tại 17:00Z | 24.000 | Đạt |
| 12 | 26 giờ, ba ngày, 26 kWh | 3.000 + 18.000 + 44.000 + 25.000 + 6.000 + 3.000 | 99.000 | Đạt |
| 13 | Ba khoảng số đo trong cùng một khung | 0,003 × 500 = 1,5 → 2; không làm tròn ba lần | 2 | Đạt |
| 14 | Hai ngày, mỗi đoạn có tiền đúng 0,5 | (0,001 × 500 → 1) + (0,001 × 500 → 1) | 2 | Đạt |
| 15 | Thành tiền nhỏ hơn 0,5 | 0,001 × 499 = 0,499 → 0 | 0 | Đạt |
| 16 | Số đo tại mốc bằng 13 kWh, đầu/cuối bằng Wh | 13 kWh = 13.000 Wh; 3 × 5.000 + 5 × 3.000 | 30.000 | Đạt |
| 17 | Không tiêu thụ điện, vẫn cắt 22:00 | 0 × 5.000 + 0 × 3.000 | 0 | Đạt |
| 18 | Số đo gần 06:00 tại 05:30 và 06:30 | Mốc 06:00 = 11.000 + 2.000 × 30/60 = 12.000 Wh; 2 × 3.000 + 4 × 4.000 | 22.000 | Đạt |
| 19 | Nội suy ra 0,5 Wh mỗi ngày, đơn giá 3.333 | Mỗi đoạn 0,0005 × 3.333 = 1,6665 → 2; 2 + 2 | 4 | Đạt |
| 20 | Qua nửa đêm, giá ngày mới đổi thành 6.000 | 4 × 3.000 + 4 × 6.000 | 36.000 | Chờ SCRUM-64/206 |
| 21 | Finishing 30 phút, ân hạn 10, phí 100/phút | Điện 8.000 + (30 − 10) × 100 | 10.000 | Chờ SCRUM-61/204 |
| 22 | Đã sạc xong, SuspendedEV với cùng thời gian ca 21 | Điện 8.000 + 20 × 100 | 10.000 | Chờ SCRUM-61/204 |
| 23 | Rút súng đúng hết 10 phút ân hạn | Điện 8.000 + 0 phút × 100 | 8.000 | Chờ SCRUM-61/204 |
| 24 | Rút súng sau 5 phút, còn trong ân hạn | Điện 8.000 + 0 phút × 100 | 8.000 | Chờ SCRUM-61/204 |

## 3. Chạy lại trên Windows

Từ thư mục gốc repo:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_scrum65_pricing.py -ra --tb=short
```

Kết quả hiện tại: **21 passed, 5 skipped**. Trong 21 test đạt có **19 ca tính tiền**,
một test kiểm tra phạm vi/metadata và một test cố ý đưa kết quả sai để kiểm tra
thông báo. Năm ca skipped là 20–24; lý do được in bằng `-ra`. Skipped không phải đạt.

Kiểm tra lại cùng luồng chốt phiên và tính kWh:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/test_scrum65_pricing.py tests/unit/test_stop_transaction.py tests/unit/test_session_energy.py -ra --tb=short
```

Kết quả: **44 passed, 5 skipped**. CI hiện đã thu thập `backend/tests`, nên file
test mới được chạy tự động khi kiểm tra PR; không cần thêm bước workflow.

Ví dụ khi tiền ca 01 bị sai một đồng, test báo cả đoạn và tổng:

```text
SCRUM65-01 — Một khung thấp điểm
Đoạn 1: amount_vnd, mong đợi 6000, thực tế 5999, chênh -1 đồng (thực tế - đáp án)
Tổng phiên: total_vnd, mong đợi 6000, thực tế 5999, chênh -1 đồng (thực tế - đáp án)
Tính tay: (12000 - 10000) / 1000 = 2 kWh; 2 × 3000 = 6000 đồng.
```

Test đối chiếu cả số đoạn, khoảng thời gian theo múi giờ trạm, tên khung giá,
điện năng, đơn giá, tiền từng đoạn và tổng. Giá trị tiền phải là số nguyên;
không cho phép sai số tiền bằng `approx` hoặc dùng số thực.

## 4. Bàn giao và điều kiện nghiệm thu

**Bộ dữ liệu và test cho phần đã hỗ trợ đã được chuẩn bị; SCRUM-65 chưa đủ điều
kiện chuyển Done.** Còn năm ca nghiệp vụ chưa chạy được, review chéo và nghiệm thu
theo DoD. Đây là bộ ca mô phỏng để kiểm tra thuật toán, chưa phải dữ liệu phiên
thu từ trụ ảo cho SCRUM-210.

Ca 20 chờ SCRUM-64/206: `calculate_session_price` hiện chỉ nhận một bộ `bands`,
còn `finalize_session_billing` chọn phiên bản có hiệu lực khi phiên bắt đầu cho
cả phiên. Nửa đêm đã chia được đoạn, nhưng chưa áp hai phiên bản giá khác nhau.

Ca 21–24 chờ SCRUM-61/204: model/hàm hiện chưa có phí theo phút, ân hạn và mốc
rút súng. Kể cả ca có phí bằng 0 cũng chưa được tính là đạt vì chưa chạy luồng
phí chiếm trụ. Các trường `idle_input`, `tariff_versions`, `idle_fee_vnd` và
`billable_idle_minutes` chỉ mô tả dữ liệu kiểm thử, không khai báo API mới.

Khi các phần trên có hàm dùng được, nối đầu vào của năm ca vào hàm thật, bổ sung
đối chiếu riêng tiền phí và số phút ở ca 21–24, rồi bỏ `blocked_by` và cập nhật
kiểm tra adapter trong `test_manual_dataset_has_required_scope_and_author`.
Không chỉ bỏ skip hoặc bỏ các đầu vào chưa được hỗ trợ để làm test xanh.
Giữ đáp án tính tay để tái sử dụng cho SCRUM-209/210; nếu nghiệp vụ được chốt khác,
ghi rõ thay đổi và nhờ Tạ Như Vinh review lại.

Sau đó chạy đủ 24 ca, thực hiện review chéo, kiểm tra GitHub CI và staging
theo DoD trước khi chuyển ticket Done. Chưa ghi nhận các bước đó là đã hoàn thành.
