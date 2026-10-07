# Kiểm thử phần code mới sau đồng bộ Sprint 3

Ngày 07/10/2026. Hướng dẫn đối chiếu với nhánh local `sprint-3`, commit gộp
`cc006ab`: code `main` ở `440a8ab`, `sprint-3` ở `4a5bbb7` và
`DANG-DAI-SCRUM-191-192-194` ở `8d9b4db`.

## 1. Khởi chạy và kiểm tra trụ ảo không cần Docker

Nếu server đang chạy từ trước khi pull, nhấn Ctrl+C rồi chạy lại. Trong PowerShell:

```powershell
Set-Location E:\TTCS_K8S4_N5
.\run.ps1
```

Giữ terminal này mở. Script chạy migration, web và fleet OCPP local; `.env`
cần có `APP_ENV=development`. Không chạy đồng thời app Docker trên cổng 8000.

Mở http://localhost:8000/login và đăng nhập tài khoản mẫu:

| Vai trò | Email | Mật khẩu development |
| --- | --- | --- |
| Quản trị | `admin@csms.local` | `Admin@2024!` |
| Vận hành | `operator@csms.local` | `Operator@2024!` |
| Tài xế | `driver@csms.local` | `Driver@2024!` |

Mở http://localhost:8000/monitoring, nhấn F5 để tải giao diện mới. Chờ fleet
kết nối rồi bấm Làm mới nếu cần.

Kết quả mong đợi: nhóm `SIM-01` đến `SIM-20` online, cùng các trụ mẫu Vincom,
AEON và Thủ Thiêm. Đây là các client WebSocket thật kết nối backend local.
`CP_AEON_FAULT` cố ý báo lỗi; `CP_DEMO_MAINT_01` cố ý báo bảo trì.

Thử tham số mới bằng cách Ctrl+C, chạy lại:

```powershell
.\run.ps1 -SimulatorCount 3 -SkipDemoStations
```

Chỉ fleet `SIM-01` đến `SIM-03` được bật. Các trụ đã seed khác vẫn có thể hiện
trong danh sách, nhưng sẽ chuyển offline sau thời gian phát hiện mất heartbeat.
Chạy lại `.\run.ps1` để quay về fleet mặc định.

## 2. Bắt đầu sạc và giữ RFID — SCRUM-191/192/194

Dùng tài khoản admin hoặc operator. Tài xế hiện chưa được mở `/monitoring`.

1. Mở `/monitoring`, chọn bộ lọc **Sẵn sàng**, mở chi tiết trạm có `SIM-01`
   hoặc `CP_VINCOM_01` online.
2. Chọn **Đầu nối 1** đang Available. Để trống RFID: nút **Bắt đầu sạc** phải
   bị khóa. Nhập `TEST-TAG` để kiểm tra thao tác gửi lệnh; thẻ này chỉ dùng thử
   giao diện, chưa chứng minh một phiên sạc đã được chấp nhận.
3. Bấm **Bắt đầu sạc**. Nút đổi thành **Đang chờ bắt đầu sạc…**, đồng thời
   dropdown đầu nối và ô RFID bị khóa. Bấm nhiều lần không gửi lệnh trùng.
4. Trong lúc còn chờ, bấm dấu × đóng chi tiết rồi mở lại cùng trạm. Đầu nối,
   RFID `TEST-TAG`, thông báo chờ và trạng thái khóa phải được giữ nguyên.
5. Sau khi nhận lỗi hoặc hết hạn, nút/ô nhập được mở lại; có thể thử lại.
6. Chuyển sang trụ lỗi hoặc bảo trì: đầu nối không Available không được gửi
   yêu cầu bắt đầu sạc.

Có thể mở F12 → Network, lọc `remote-start` để kiểm tra:

- Một lần bấm tạo một POST tới `/api/charge_points/<mã trụ>/remote-start`.
- Payload gồm `connector_id` và `id_tag` đã nhập.
- Thử lại sau khi yêu cầu trước kết thúc tạo một POST mới.

**Giới hạn hiện tại:** fleet mặc định chỉ phản hồi Reset, chưa phản hồi
`RemoteStartTransaction`. Vì vậy trên máy local thường nhận HTTP 504 sau timeout
backend, mặc định 30 giây. Frontend giới hạn tổng thời gian chờ tối đa 60 giây;
lỗi backend đến sớm hơn sẽ kết thúc chờ sớm hơn. Không cần chờ đúng 60 giây
để kết luận bước đóng/mở lại RFID đạt.

Không kỳ vọng bấm nút này sẽ tạo được phiên sạc thành công với fleet mặc định.
Accepted chỉ có nghĩa trụ nhận lệnh; frontend còn phải tìm thấy phiên mới đúng
trụ/đầu nối. Những ca Accepted, Rejected, HTTP 409, hết 60 giây, phản hồi muộn,
thử lại và điều hướng theo quyền được kiểm tra bằng bộ test JS ở mục 5.

## 3. Trang đối chiếu kWh — SCRUM-184

Dùng admin hoặc operator, vào **Phiên sạc** rồi bấm **Đối chiếu kWh**.
Nút **Phiên sạc** trên trang đối chiếu đưa bạn trở lại danh sách. Tài xế
không thấy nút đối chiếu. Có thể mở trực tiếp:

http://localhost:8000/sessions/kwh-reconciliation

| Thao tác | Kết quả mong đợi với dữ liệu mẫu hiện tại |
| --- | --- |
| Mở trang | Hiện cảnh báo đang sử dụng dữ liệu mẫu; có 20 phiên |
| Xem màu và chữ | Nền sáng, chữ/số rõ; bảng, ô tìm kiếm và thẻ tổng kết cùng tông màu |
| Xem tổng kết | 20 khớp, 0 lệch, 100%; System và Simulator cùng 372.450 kWh |
| Bấm Khớp | Hiện cả 20 phiên |
| Bấm Lệch hoặc Thiếu CSMS | Danh sách rỗng vì mẫu hiện tại không có các ca này |
| Chọn Tất cả, tìm `CP01` | Chỉ hiện dòng có mã trụ khớp |
| Tìm mã không tồn tại | Hiện trạng thái không có kết quả |
| Bấm tiêu đề cột kWh hoặc mã trụ hai lần | Đổi thứ tự tăng/giảm |
| Bấm CSV và Markdown | Tải file có các dòng đang được lọc trên màn hình |

Xóa nội dung tìm kiếm và chọn Tất cả trước khi muốn xuất đủ 20 dòng.

Hiện chưa có route backend `/api/reconciliation/kwh`; frontend gọi thử rồi
đọc `/static/data/kwh_reconciliation_sample.json`. HTTP 404 của API này trong
Network là nguyên nhân fallback. Số liệu trên trang chưa phải kết quả của lượt
chạy kịch bản SCRUM-182 trên máy bạn.

## 4. Danh sách trạm dành cho tài xế

Đăng xuất rồi đăng nhập `driver@csms.local` / `Driver@2024!`. Mở:

http://localhost:8000/stations

- Trang mở được, có nội dung **Danh sách các trạm đang hoạt động**.
- Chỉ hiện trạm có trạng thái active, không hiện trạm tạm dừng/bảo trì/khóa.
- Có thể tìm kiếm và làm mới; không có nút Thêm/Sửa/Xóa trạm.
- Bộ lọc chỉ có trạng thái đang hoạt động.

Trong F12 → Network, response `/api/stations` cho tài xế không chứa `owner_id`
hoặc thông tin tài khoản chủ trạm. Nếu không có trạm active thì danh sách rỗng
là hợp lệ. Phần này kiểm tra quyền xem danh sách; chưa phải luồng tài xế bắt đầu
sạc trên trang monitoring.

## Trang phiên bất thường và nhật ký sau cập nhật main

Dùng admin hoặc operator, mở `/sessions/anomalies` và `/audit`. Có thể kiểm tra
trang tải được, hiển thị các cột và các nút lọc.

Bản `api_client.js` lấy từ main đang trả dữ liệu cố định cho hai trang này:
`listAnomalies` trả 3 phiên mẫu, `listAuditLogs` trả 2 bản ghi mẫu. Hai hàm hiện
không gọi endpoint backend tương ứng. Vì vậy không dùng các bảng này để kết luận
đã ghi nhận phiên bất thường mới hoặc log của lệnh vừa gửi; tham số lọc gửi vào
hai hàm cũng chưa được dùng để truy vấn dữ liệu thật.

## 5. Test tự động nhanh

Mở một terminal PowerShell khác tại thư mục gốc. Các test này không cần Docker
và không cần dùng database đang phục vụ web.

```powershell
Set-Location E:\TTCS_K8S4_N5
node --test tests/frontend_behavior.cjs
```

Với bản code này, kết quả đã kiểm tra là **65 pass, 0 fail**. Bao gồm hành vi
giám sát cũ và các ca SCRUM-191/192/194 mới. Bộ test này chưa kiểm thử trang
đối chiếu kWh trên trình duyệt; vẫn cần thực hiện mục 3.

Kiểm tra backend liên quan đến lệnh từ xa, quyền, simulator và hàm đối chiếu:

```powershell
Push-Location E:\TTCS_K8S4_N5\backend
try {
    ..\.venv\Scripts\python.exe -m pytest tests/unit/test_remote.py tests/unit/test_ownership.py tests/unit/test_ocpp_simulator.py tests/unit/test_kwh_reconciliation.py --tb=short -q
} finally {
    Pop-Location
}
```

Hàm đối chiếu backend được test riêng; các test đó chưa chứng minh frontend
đã nối API thật. Nếu môi trường chưa cài pytest, cài:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio
```

## 6. Kịch bản 20 trụ ngắt/nối và kWh — SCRUM-182

File mới `tests/test_scrum182_20charger_scenario.py` dùng Docker/PostgreSQL và
client OCPP của riêng bài test. `.\run.ps1` không cung cấp stack cho file này.
Mở Docker Desktop, đợi engine hoạt động rồi dùng stack thử nghiệm:

```powershell
Set-Location E:\TTCS_K8S4_N5
docker compose --env-file .env.example -p csms-scrum182 -f docker-compose.acceptance.yml up -d --build --wait db app
.\.venv\Scripts\python.exe -m pytest tests/test_scrum182_20charger_scenario.py --docker-project csms-scrum182 -v -s --tb=short
```

Lệnh test có 2 ca: 20 trụ với ngắt/nối giữa phiên, và smoke test 3 trụ. Sau lượt
20 trụ thành công, kiểm tra `ketqua/scrum182_kwh_result.json`: 20 bản ghi,
`summary.all_passed` bằng true, kWh trong DB khớp simulator trong ngưỡng 0.001.

Bài test đã được sửa để đọc RFID hợp lệ của `driver@csms.local` từ database
acceptance thay vì cố định `DRIVER-TAG-01`. Nếu seed thiếu thẻ, bài test báo lỗi
rõ ràng. CI chạy kịch bản này sau khi khởi động Docker/PostgreSQL; bước unit
test không cần stack Docker.

Lượt kiểm tra local ngày 07/10/2026 đã đạt **11/11 test Docker**, gồm cả hai
ca SCRUM-182. Kết quả 20 trụ: **20 khớp, 0 lệch**, `summary.all_passed=true`.
Các bước kiểm tra còn lại đạt **429 test Python**, **65 test frontend**,
Ruff, Mypy và kiểm tra lỗ hổng thư viện. Database thử nghiệm chạy trên image
Python 3.11; tiến trình pytest local dùng Python 3.14.

JSON SCRUM-182 cũng có schema khác JSON mẫu mà trang đối chiếu đang đọc;
chưa tự xuất kết quả trực tiếp lên trang SCRUM-184.

Khi xong, dừng riêng stack thử nghiệm:

```powershell
docker compose --env-file .env.example -p csms-scrum182 -f docker-compose.acceptance.yml down
```

Stack này dùng database tmpfs; dữ liệu thử nghiệm không được giữ sau khi dừng.

## Ghi kết quả để đối chiếu

Với mỗi ca, ghi tài khoản/vai trò, mã trụ, đầu nối, thao tác, kết quả mong đợi
và kết quả thực tế. Nếu có lỗi, ghi thông báo trên giao diện và HTTP status trong
F12 → Network. Khi test thất bại, giữ phần lỗi cuối terminal để xác định lỗi môi
trường, dữ liệu seed hay hành vi của chức năng.
