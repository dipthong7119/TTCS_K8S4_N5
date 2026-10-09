# Kiểm tra T-43, T-45, T-53 và SCRUM-188

Ngày triển khai: **09/10/2026**. Đây là ba task và phần dữ liệu mẫu thuộc
Tạ Như Vinh trong `huongdan/Phan_cong_Sprint3.md`.

| Task | Hành vi cần kiểm tra |
| --- | --- |
| T-43 / SCRUM-168 | Gửi số đo mới → cũ → trùng qua WebSocket. DB chỉ giữ số đo mới; đúng một cảnh báo cho số đo cũ. |
| T-45 / SCRUM-170 | StopTransaction muộn đóng đúng phiên cũ; giữ thời điểm của trụ, chốt kWh từ meterStop − meterStart; lọc transactionData cũ/trùng. |
| T-53 / SCRUM-174 | Job đánh dấu phiên offline quá ngưỡng hoặc lệnh dừng quá hạn, không tự đóng phiên. Chạy hai lần không đổi lại phiên hay phát thông báo trùng. |
| SCRUM-188 | Ba phiên tính tay dùng chung để kiểm tra hàm thuần và StopTransaction. |

## 1. Ba phiên tính tay

Dữ liệu ở `backend/tests/scrum188_sessions.json`. Đáp án là giá trị cố định,
không sinh bằng hàm đang được kiểm tra. Đơn vị hai số đo đầu/cuối là **Wh**.

| Ca | Số đo đầu | Số đo cuối | Tính tay | Kết quả |
| --- | ---: | ---: | --- | --- |
| Thường | 18.340 | 30.685 | (30.685 − 18.340) / 1.000 | `12.345 kWh`, completed |
| Số đo lùi | 27.110 | 26.000 | Chênh lệch −1.110 Wh | kWh null, needs_review, negative_kwh |
| Bằng nhau | 40.520 | 40.520 | 0 / 1.000 | `0.000 kWh`, completed |

Test thêm cả ba trạng thái ban đầu `active`, `anomaly`, `needs_review` khi
nhận StopTransaction muộn. Phiên thường và phiên bằng nhau đóng bình thường;
phiên số đo lùi vẫn phải kiểm tra, không lưu điện năng âm.

## 2. Kiểm tra nhanh trên Windows

Chạy PowerShell ở thư mục repo, đã cài `backend/requirements-dev.txt` trong `.venv`:

```powershell
Set-Location E:\TTCS_K8S4_N5\backend
& ..\.venv\Scripts\python.exe -m pytest tests/unit/test_session_energy.py tests/unit/test_stop_transaction.py tests/unit/test_session_review_jobs.py --tb=short -q
& ..\.venv\Scripts\python.exe -m pytest ../tests/test_sprint2_network.py -k "t43 or t45_t53" --tb=short -q
```

Lệnh đầu: **37 test**. Lệnh sau: **2 test**, khởi chạy server riêng, DB SQLite
tạm và WebSocket thật. Không đăng nhập hoặc thay dữ liệu ứng dụng ở cổng 8000.

**T-43:** test dùng ba mã tin nhắn khác nhau để kiểm tra chống trùng theo số đo,
không chỉ theo messageId. Chỉ còn số đo 30.685 Wh lúc 08:03 UTC; log có một
dòng `Meter value rejected` cho số đo 08:02. Bản gửi trùng không có cảnh báo mới.

**T-45/T-53:** test tạo phiên 18.340 Wh, lưu số đo 19.340 Wh, ngắt kết nối.
Ngưỡng của server test là 60 giây. Test đưa thời điểm liên lạc cuối của riêng
trụ test về 61 giây trước để job chạy thật mà không phải đợi một phút.
Phiên xuất hiện trong API bất thường, vẫn chưa có ended_at/meterStop.
Trụ nối lại và gửi StopTransaction với 30.685 Wh cùng transactionData dồn.
Kết quả là một phiên completed, 12.345 kWh và ba số đo 19.340, 26.340,
30.685 Wh. Gửi lại cùng messageId hoặc messageId mới không thay kết quả.
Thời điểm `15:03 +07:00` của thiết bị được lưu thành `08:03 UTC`.

Test đơn vị còn kiểm tra ngưỡng 59/60/61 giây, trụ chưa từng liên lạc,
lệnh dừng 119/120/121 giây, giữ lý do kiểm tra cũ, và chỉ trừ ví một lần:
1.000 kWh × 1.000 đồng/kWh = 1.000 đồng.
Ca đổi khung giá dùng mốc số đo đã lưu: 0.200 kWh × 1.000 đồng +
0.800 kWh × 2.000 đồng = 1.800 đồng, kể cả khi mốc đó được gửi trùng trong Stop.

## 3. Kiểm tra PostgreSQL và Docker

Dùng tên project riêng và cổng ngẫu nhiên để giữ nguyên ứng dụng local:

```powershell
Set-Location E:\TTCS_K8S4_N5
docker compose --env-file .env.example -p csms-vinh-test -f docker-compose.acceptance.yml up -d --build --wait --wait-timeout 90 db app
& .\.venv\Scripts\python.exe -m pytest tests/sprint2_docker_acceptance.py::test_t43_t45_t53_postgres_offline_session_recovers_with_late_stop --docker-project csms-vinh-test --tb=short -v
docker compose --env-file .env.example -p csms-vinh-test -f docker-compose.acceptance.yml down -v --remove-orphans
```

Test này chạy cùng luồng mới → cũ → trùng, offline → job → danh sách bất thường
→ nối lại → Stop muộn trên PostgreSQL, có trụ WebSocket độc lập. Mỗi lần test
tạo mã trụ riêng; chạy lại không phụ thuộc bản ghi của lần trước.
Lệnh cuối chỉ xoá môi trường test `csms-vinh-test` và DB tạm của nó.

Kịch bản 20 trụ kiểm tra tác động lên các handler dùng chung:

```powershell
& .\.venv\Scripts\python.exe scripts/run_sprint3_ci.py --repeat 3
```

Script tự build, tạo và dọn stack riêng; kết quả ở `outputs/sprint3-ci/`.

## 4. Thử danh sách bất thường trên web

Chạy ứng dụng bằng code mới. Với Docker local, build lại backend bằng
`docker compose up -d --build app`; nếu dùng `run.ps1`, khởi động lại server.
Nhấn Ctrl + F5 trên trình duyệt để tải API client mới.

Mặc định phải offline **6 giờ** mới bị đánh dấu; Reset một trụ rồi trụ trở lại
online ngay sẽ không tạo phiên bất thường. Để thử nhanh, đặt trong cấu hình
**môi trường thử**, rồi khởi động lại backend:

```dotenv
SESSION_OFFLINE_GRACE_SECONDS=60
OCPP_JOB_POLL_SECONDS=1
```

1. Dùng tài khoản admin/operator. Bắt đầu một phiên, ghi lại mã trụ và mã phiên.
2. Ngắt simulator của trụ đó và giữ offline hơn 60 giây.
3. Mở **Phiên bất thường**, chọn khoảng thời gian chứa phiên, bấm làm mới.
   Phiên phải có lý do **Trụ ngoại tuyến** và vẫn chưa có thời gian kết thúc.
4. Kiểm tra luồng Stop muộn bằng test WebSocket ở mục 2/3: sau Stop hợp lệ,
   mã phiên cũ biến mất khỏi danh sách và số kWh vẫn khớp bảng tính tay.
5. Sau khi thử, đưa ngưỡng về 21.600 giây và chu kỳ job về 60 giây.

Trạng thái từ job được ghi vào bảng phiên; thông báo SSE chỉ gửi sau commit.
Trường hợp hết hạn lệnh dừng và offline đồng thời giữ lý do
`remote_stop_timeout`, không ghi đè bằng `offline`.

## 5. Kiểm tra toàn dự án

```powershell
Set-Location E:\TTCS_K8S4_N5\backend
& ..\.venv\Scripts\python.exe -m ruff check app tests alembic ../tests ../scripts
& ..\.venv\Scripts\python.exe -m mypy app
& ..\.venv\Scripts\python.exe -m pip_audit --local --progress-spinner off
& ..\.venv\Scripts\python.exe -m pytest tests ../tests --ignore=../tests/test_scrum182_20charger_scenario.py --tb=short -q
Set-Location ..
node --test tests/frontend_behavior.cjs
```

Test WebSocket nằm trong bộ pytest tự phát hiện; test PostgreSQL nằm trong
bước Docker acceptance của workflow CI hiện có. Chưa có kết quả review của
thành viên khác hoặc nghiệm thu trên staging trong lần kiểm tra local này.
