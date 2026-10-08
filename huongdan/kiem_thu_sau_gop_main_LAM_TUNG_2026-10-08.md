# Kiểm thử sau gộp main và LAM-TUNG ngày 08/10/2026

## Code đã nhận và lịch sử commit

- Nhánh đang làm việc: `sprint-3`.
- `main`: `89813d5`, đã có trên máy từ lần đồng bộ trước.
- `LAM-TUNG`: `5f281c8`, commit `scrum 169` của Nguyễn Lâm Tùng.
- Gộp bằng fast-forward: giữ nguyên mã commit, tác giả, ngày và nội dung commit
  gốc. Các sửa lỗi kiểm tra và tài liệu được đặt trong commit mới, không amend,
  rebase, squash hoặc cherry-pick commit của thành viên.
- Nhánh dự phòng trước lần gộp này:
  `codex/backup-sprint-3-2026-10-08-before-lam-tung`.

## 1. Phần mới của LAM-TUNG — SCRUM-169 / T-44

Đây là logic backend đối chiếu phiên sạc khi trụ nối lại. Không thêm trang hoặc
nút mới. Server đọc các phiên chưa có thời điểm kết thúc từ database và khớp
đúng trụ, đầu nối và ID phiên (`transactionId`).

| Tình huống khi kết nối lại | Kết quả mong đợi |
| --- | --- |
| Trụ báo `Charging`, `SuspendedEV` hoặc `SuspendedEVSE` | Giữ phiên đang mở và ID cũ; không tạo phiên trùng. |
| Trụ báo `Available` nhưng phiên đang `active` chưa kết thúc | Chuyển phiên thành `needs_review`, lý do `connector_available_after_reconnect`; không tự đóng phiên hoặc tính kWh cuối. |
| Phiên đã là `needs_review` hoặc `anomaly` | Không ghi đè trạng thái hoặc lý do kiểm tra đã có. |
| Trụ báo `Preparing`, `Finishing`, `Reserved`, `Unavailable` hoặc `Faulted` | Chưa kết luận; tiếp tục chờ trạng thái đủ để đối chiếu. |
| Báo `Charging` nhưng không có phiên mở | Ghi log INFO; không tự tạo phiên mới. |
| Mất WebSocket hoặc bị đánh dấu offline | Phiên vẫn mở. Khi nối lại, dựng lại danh sách phiên từ database. |
| Gửi tiếp `MeterValues` rồi `StopTransaction` với ID cũ | Số đo vẫn thuộc phiên cũ; phiên được hoàn tất khi nhận Stop hợp lệ. |

### Chạy kiểm thử phần mới

Mở PowerShell tại thư mục dự án. Nếu chưa cài thư viện kiểm thử, chạy một lần:

```powershell
Set-Location E:\TTCS_K8S4_N5
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

Chạy bộ kiểm thử đối chiếu phiên:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/unit/test_session_reconciliation.py -v --tb=short
```

Kết quả mong đợi: **25 passed**. Các test dùng SQLite trong bộ nhớ; không cần
chạy web/Docker và không ghi vào database của ứng dụng đang dùng.

Để xem riêng luồng WebSocket mở → ngắt → nối lại, cùng log KEEP/FLAG:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/unit/test_session_reconciliation.py -k websocket_reconnect -vv --log-cli-level=DEBUG --tb=short
```

Kết quả mong đợi: **2 passed**. Một ca gửi `Charging` và giữ phiên `active`;
một ca gửi `Available` và chuyển thành `needs_review`. Cả hai đi qua endpoint
WebSocket của ứng dụng, kiểm tra đúng ID, không đóng phiên và chỉ có một phiên
trong database kiểm thử. Dữ liệu kiểm thử này không xuất hiện trên web đang chạy.

Các ca riêng khác:

```powershell
# Mất kết nối không tự kết thúc phiên
.\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/unit/test_session_reconciliation.py -k offline_charge_point_job -v --tb=short

# Nối lại rồi gửi số đo và StopTransaction với ID cũ
.\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/unit/test_session_reconciliation.py -k offline_message_rebuilds -v --tb=short

# Available đánh dấu cần xem xét đúng một lần
.\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/unit/test_session_reconciliation.py -k available_flags_once -v --tb=short
```

### Quan sát trên web khi có phiên OCPP thực tế

Khởi động lại server đã chạy từ trước khi pull. Chạy local trên Windows:

```powershell
Set-Location E:\TTCS_K8S4_N5
.\run.ps1
```

Đăng nhập tại <http://localhost:8000/login> bằng tài khoản development
`operator@csms.local` / `Operator@2024!`, hoặc
`admin@csms.local` / `Admin@2024!`.

1. Với client OCPP đang chạy một phiên, ghi lại ID phiên trên `/sessions`.
   Ngắt client giữa phiên mà không gửi `StopTransaction`.
2. Kết nối lại cùng mã trụ, gửi `BootNotification`, rồi `StatusNotification`
   cho đúng đầu nối. Ca `Charging` phải giữ ID cũ và phiên đang mở.
3. Với một phiên thử khác, lặp lại nhưng gửi `Available` sau khi kết nối lại.
   Xem `/api/sessions?status=needs_review` và `/sessions/anomalies`: phiên đó
   phải có trạng thái `needs_review`, `ended_at` vẫn null và chưa có kWh cuối.
   Tại trang bất thường, chọn tất cả lý do để tránh bộ lọc che mất phiên.
4. Gửi `MeterValues` và `StopTransaction` với `transactionId` ban đầu.
   Xem lại `/sessions`: phiên được hoàn tất, không xuất hiện phiên thứ hai.

Fleet mặc định của `run.ps1` gửi Boot/Status/Heartbeat và trả lời Reset;
chưa tự tạo phiên sạc hoặc xử lý RemoteStart/RemoteStop. Vì vậy chỉ bấm Reset
trên trụ chưa có phiên không đủ để thử T-44. Dùng các lệnh kiểm thử ở trên
để tái hiện đầy đủ mà không cần tự viết client OCPP. Nếu dùng client riêng,
chạy `.\run.ps1 -SkipSimulator` để tránh hai client cùng chiếm một mã trụ.

Lý do `connector_available_after_reconnect` hiện được lưu ở database/log;
API và giao diện chưa hiển thị riêng trường `review_reason`. Có thể kiểm chứng
lý do chính xác bằng test `available_flags_once` ở trên.

## 2. Bản sửa đã nhận từ main — giới hạn chờ bắt đầu sạc

Commit `202a6ab` của Đặng Ngọc Đại, đã gộp vào main qua PR #43:

- Phản hồi đến sau mốc 60 giây không được báo sạc thành công, kể cả khi timer
  chạy trễ.
- Rời trang giải phóng trạng thái chờ; khi quay lại có thể thử lại.
- Phản hồi cũ không được ghi đè lần thử mới.

Chạy kiểm thử:

```powershell
Set-Location E:\TTCS_K8S4_N5
node --test tests/frontend_behavior.cjs
```

Kết quả mong đợi: **76 passed**. Các ca mới có tên bắt đầu bằng
`SCRUM-191: delayed...` và `SCRUM-191: returning after pagehide...`.
Các ca này chủ động điều khiển thời gian và phản hồi để kiểm tra chính xác
mốc 60 giây; không cần ngồi chờ hoặc thay đổi dữ liệu thật.

## 3. Kiểm tra toàn bộ sau gộp

```powershell
Set-Location E:\TTCS_K8S4_N5\backend
..\.venv\Scripts\python.exe -m ruff check app tests alembic ../tests ../scripts
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest tests ../tests --ignore=../tests/test_scrum182_20charger_scenario.py --tb=short -q
```

Mong đợi Ruff/Mypy không lỗi và **494 passed**. Bộ này có cả kiểm thử migration
trên database tạm; không cần cập nhật database thật để chạy test.

Kiểm thử 20 trụ ngắt/nối bằng PostgreSQL cần mở Docker Desktop trước:

```powershell
Set-Location E:\TTCS_K8S4_N5
.\.venv\Scripts\python.exe scripts/run_sprint3_ci.py --repeat 1
```

Runner tự build ứng dụng, tạo stack riêng, chạy 20 trụ rồi dọn stack đó.
Kết quả mong đợi là `PASSED`; báo cáo nằm trong `outputs/sprint3-ci/`.
Lúc đồng bộ ngày 08/10, Docker Engine chưa chạy nên chưa xác nhận được ca này.

## 4. Kiểm tra commit gốc còn nguyên

```powershell
Set-Location E:\TTCS_K8S4_N5
git show -s --format=fuller 5f281c8
git log --oneline --decorate -5
git status --short --branch
```

`5f281c8` vẫn có tác giả Nguyễn Lâm Tùng và thông điệp `scrum 169`.
Sau lần đồng bộ này, thay đổi nằm trên nhánh local `sprint-3`; chưa push
lên GitHub.
