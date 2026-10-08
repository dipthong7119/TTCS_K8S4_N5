# T-56 / SCRUM-116 và SCRUM-185 — Trịnh Thanh Tùng

Phạm vi: bước CI 20 trụ, đọc kết quả, chặn merge khi thất bại và đóng gói
kịch bản CI. Bám vào T-55, kịch bản SCRUM-182 và công cụ đối chiếu SCRUM-183
đã có trong bản đồng bộ `07aeee4`; không thay handler nghiệp vụ của thành viên khác.

## Phần triển khai

- `scripts/run_sprint3_ci.py`: cùng một lệnh chạy trên Windows và Linux CI,
  build/dùng image đã build, khởi tạo PostgreSQL/app riêng, chạy và dọn stack.
- 20 trụ cho mỗi lượt, mỗi trụ ngắt/nối ngẫu nhiên 1–3 lần; 3 lượt với seed
  42/43/44. Giữ `transactionId` khi nối lại, không gọi StartTransaction lần hai.
- Kiểm tra một phiên cho mỗi trụ, phiên đã hoàn tất, đủ MeterValues theo đúng
  phiên và kWh dương khớp simulator trong sai số 0.001 kWh.
- Log nêu `session`, mã trụ, kWh mong đợi/thực tế, độ lệch, số lần nối lại
  và nguyên nhân lỗi. JSON kết quả vẫn được xuất khi phát hiện lỗi phiên.
- Adapter gọi trực tiếp `reconcile_datasets` / `export_markdown_table` của
  SCRUM-183, xuất JSON/Markdown đúng hợp đồng của SCRUM-184.
- Artifact CI `sprint3-20-charger-evidence` giữ 14 ngày, luôn lưu khi bước
  kịch bản đã chạy, gồm cả log, JUnit, báo cáo và manifest thất bại.
- Không retry test thất bại; chỉ retry tải PostgreSQL khi registry lỗi mạng.
- Timeout kịch bản 240 giây, bước CI giới hạn 5 phút. Có bước cleanup dự phòng
  nếu runner bị GitHub hủy hoặc timeout.

## Gate GitHub

`.github/workflows/ci.yml` có job tên **Sprint 3 CI**, chạy cho push, PR và
workflow được CD gọi lại. Bước kịch bản nằm sau unit test, không dùng
`continue-on-error` hoặc điều kiện bỏ qua lỗi.

Profile `.github/sprint3-branch-protection.json` bắt buộc check **Sprint 3 CI**
do app `github-actions` (15368) cung cấp, yêu cầu nhánh cập nhật với nhánh đích,
áp dụng cả quản trị viên, không cho force push hoặc xóa nhánh được bảo vệ.
Không thêm yêu cầu review của người khác ngoài phạm vi công việc này.

## Chạy lại local

Mở Docker Desktop, tại thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe scripts/run_sprint3_ci.py
```

Lệnh sẽ tạo project mới và tự dọn. Có thể dùng image đã build:

```powershell
.\.venv\Scripts\python.exe scripts/run_sprint3_ci.py --image csms-app:ci --no-build
```

Đọc `outputs/sprint3-ci/<run-id>/manifest.json`: cần `verdict=PASSED`, đủ
3 mục `runs`, mỗi mục có 20 phiên khớp và `elapsed_seconds < 300`.
Mỗi `run-N` chứa `scenario.json`, `reconciliation.json`, `reconciliation.md`,
`pytest.log` và `junit.xml`. Bộ dữ liệu thật này chưa tự thay dữ liệu mẫu trên
trang `/sessions/kwh-reconciliation`; có thể tải từ artifact để bàn giao cho
SCRUM-183/184/186.

## Kết quả kiểm tra

Ngày 07/10/2026, trên Windows/Python 3.14 với app Docker Python 3.11:

| Kiểm tra | Kết quả |
| --- | --- |
| Ruff toàn bộ app/tests/scripts | Đạt |
| Mypy | Đạt, 46 file |
| Unit test Python | 448 đạt, bao gồm 19 test mới cho gói CI |
| Seed 42 | 20/20 phiên khớp, không mất/nhân đôi số đo |
| Seed 43 | 20/20 phiên khớp, không mất/nhân đôi số đo |
| Seed 44 | 20/20 phiên khớp, không mất/nhân đôi số đo |
| Toàn bộ gói Docker (3 lượt + startup + cleanup) | 34.61 giây, PASSED |
| Image cố ý làm sai khôi phục phiên | 20/20 phiên sai kWh, lệnh trả exit code 1 |
| Báo cáo khi thất bại | Có JSON, Markdown, JUnit, log từng phiên và log Docker |

Thử lỗi bằng image acceptance riêng: BootNotification khi nối lại cố ý cộng
1000 Wh vào mốc đầu của phiên đang mở. CI phát hiện sai lệch 1–3 kWh đúng với
số lần nối lại. Ví dụ `SCRUM182-SIM-02`, phiên 7: kỳ vọng **10.069 kWh**,
hệ thống **7.069 kWh**, chênh lệch **3.000 kWh**. Báo cáo FAILED vẫn được lưu
và stack được dọn; image lỗi không được đưa vào app/nhánh chạy chính.

Status CI và kết quả GitHub thay đổi theo commit; xem check **Sprint 3 CI**
và artifact **sprint3-20-charger-evidence** trên Actions của commit đang xét.
Profile bảo vệ nhánh là cấu hình GitHub bên ngoài Git, cần kiểm tra trực tiếp
trên Settings → Branches của cả `main` và `sprint-3` sau khi áp dụng.
