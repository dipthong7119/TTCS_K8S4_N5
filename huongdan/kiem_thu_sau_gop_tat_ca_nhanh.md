# Kiểm thử lần lượt sau khi gộp các nhánh — 09/10/2026

Nhánh kiểm thử: `codex/integration-all-branches-20261009`.
Các nhánh được gộp bằng merge, giữ nguyên mã commit và tác giả. Báo cáo đồng bộ
và kết quả tự động nằm ở `ketqua/dong_bo_tat_ca_nhanh_2026-10-09.md`.

Thực hiện từng mục, ghi kết quả thực tế rồi mới chuyển sang mục tiếp theo.
Không coi một chức năng đạt chỉ vì trang tải được hoặc unit test đạt.

## 0. Khởi chạy và chuẩn bị

PowerShell tại thư mục repo:

```powershell
Set-Location E:\TTCS_K8S4_N5
git branch --show-current
.\run.ps1
```

Nhánh phải đúng tên ở đầu tài liệu. Script chạy migration, web tại
<http://localhost:8000/login>, 20 trụ SIM và 5 trụ demo. Giữ terminal này mở.
Nếu server đã chạy sẵn thì mở URL, không chạy thêm một server trên cùng cổng.
Nếu đang dùng Docker Compose thay vì `run.ps1`, giữ cách chạy hiện tại. Để bật
simulator cùng trụ Vincom khi chúng chưa online, chạy trong PowerShell tại repo
(thao tác này có thể khởi động lại simulator, nên làm trước các phiên kiểm thử):

```powershell
$qaPreviousDemo = $env:CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS
try {
    $env:CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS = 'true'
    docker compose --profile ocpp-simulator up -d --no-deps --build simulator
} finally {
    $env:CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS = $qaPreviousDemo
}
```

Compose local gắn thư mục `frontend` trực tiếp; sau khi cập nhật menu, tải lại
trang bằng Ctrl+F5. Không cần chạy thêm `run.ps1` khi Docker đang chiếm cổng 8000.
Database local đã được nâng cấp và có bản sao lưu trước nâng cấp ở
`outputs/sprint3-ci/integration-20261009/csms-before-sync.db`. Với lần nâng cấp
khác sau này, khi server đã dừng, có thể sao lưu DB:

```powershell
if (Test-Path backend\csms.db) {
    .\.venv\Scripts\python.exe -c "import sqlite3; s=sqlite3.connect('backend/csms.db'); d=sqlite3.connect('outputs/sprint3-ci/csms-before-integration.db'); s.backup(d); d.close(); s.close()"
}
```

| Vai trò | Email | Mật khẩu demo |
| --- | --- | --- |
| Quản trị | admin@csms.local | Admin@2024! |
| Chủ trạm | owner@csms.local | Owner@2024! |
| Vận hành | operator@csms.local | Operator@2024! |
| Kế toán | accountant@csms.local | Accountant@2024! |
| Tài xế | driver@csms.local | Driver@2024! |

Đây là tài khoản development. Dùng tab riêng tư hoặc đăng xuất khi đổi vai trò.
Ghi theo mẫu: `TC | vai trò | trạm/trụ/phiên | thao tác | mong đợi | thực tế | PASS/FAIL`.
Nếu lỗi, ghi thông báo và HTTP status trong F12 → Network.

## 1. Đăng nhập, đăng xuất và phân quyền — S-02/S-03

1. Mở `/login`, thử bỏ trống email/mật khẩu: có validation, không đăng nhập.
2. Bật/tắt nút mắt: mật khẩu đổi giữa hiện và ẩn.
3. Dùng admin với một mật khẩu sai: hiện thông báo lỗi, vẫn ở trang đăng nhập.
4. Nhập đúng `Admin@2024!`: vào `/monitoring`, hiện đúng tên/vai trò.
5. Đăng xuất: về `/login`; tải lại trang được bảo vệ phải yêu cầu đăng nhập.
6. Lần lượt đăng nhập owner, operator, accountant, driver. Trang mặc định tương
   ứng: `/stations`, `/monitoring`, `/wallet`, `/sessions/mine`.
7. Tài xế mở `/stations/new`: bị chặn 403. Tài xế mở `/monitoring`: được phép,
   chỉ thấy trạm đang hoạt động theo cập nhật HOANG-DUC.

Chỉ thử sai một lần ở app dùng chung; bài khóa tài khoản/IP đã có test riêng.

## 2. Tạo, sửa, lọc trạm và quyền sở hữu — S-04

1. Đăng nhập owner, vào `/stations`, tạo trạm có tên `QA 09-10`, địa chỉ thử,
   điền các trường bắt buộc; lưu phải đưa trạm vào danh sách.
2. Sửa tên/địa chỉ rồi F5: giá trị mới được giữ.
3. Thử thiếu tên và công suất âm: bị chặn, không tạo bản ghi sai.
4. Tìm theo tên, lọc trạng thái: kết quả khớp điều kiện.
5. Tạm dừng trạm thử; đăng nhập driver: trạm này không có trong danh sách active.
6. Owner không được sửa trạm thuộc chủ khác; admin được quản lý theo quyền.
7. Thử xóa trên trạm QA không có dữ liệu phụ thuộc; không xóa trạm demo đang dùng
   cho các ca sau. Trạm có dữ liệu phụ thuộc có thể bị server chặn theo nghiệp vụ.

## 3. Khai báo trụ và đầu nối — S-05/S-06

1. Owner mở sửa trạm QA, thêm trụ mã `QA-20261009-01`, chọn 2 đầu nối.
2. Lưu: trụ xuất hiện, có đúng số đầu nối.
3. Thêm lại cùng mã: bị báo trùng, không tạo trụ thứ hai.
4. Trụ QA chưa có client OCPP kết nối nên offline/unknown là đúng.
5. Xóa trụ QA chưa có phiên để kiểm tra xóa; xác nhận riêng thao tác này.

## 4. Giám sát, bộ lọc và Reset — T-24/T-25/T-35

1. Admin/operator mở `/monitoring`, chờ fleet kết nối.
2. Nhóm `SIM-01`–`SIM-20` online; có thêm 5 trụ demo khi dùng run.ps1 mặc định.
3. Chọn **Lỗi**: thấy `CP_AEON_FAULT`, không kéo theo `CP_AEON_01` khỏe.
4. Chọn **Tạm ngừng / Bảo trì**: thấy `CP_DEMO_MAINT_01`.
5. Tìm `SIM-01`; thử lưới/danh sách, mở chi tiết, đóng bằng X/Esc/bấm ngoài.
6. Admin/operator Reset Soft một trụ SIM online: có phản hồi, trụ nối lại.
   Reset Hard kiểm tra tương tự. Trụ lỗi/bảo trì giữ profile thử sau Reset.
7. Owner/driver không có quyền Reset. Ô tổng lỗi không đếm trùng theo đầu nối.

## 5. Lưu biểu giá và ngày hiệu lực — SCRUM-61/SCRUM-206

1. Admin/owner vào `/stations`, mở **Sửa** trạm Vincom.
2. Tại thẻ biểu giá, nhập tên `QA 4000`, điện **4000 đồng/kWh**, phí chiếm trụ
   **0**, ân hạn **0**, để trống hiệu lực để áp dụng ngay; lưu.
3. Lịch sử có bản mới. F5: giá vẫn là 4000, thời điểm hiển thị theo múi giờ trạm.
4. Thử giá/phí/ân hạn âm hoặc số lẻ: bị chặn.
5. Tạo một phiên bản giá khác có hiệu lực ngày mai: lưu được; không áp vào phiên
   hôm nay. Ngày hiệu lực trong quá khứ phải bị chặn.
6. Owner không được lưu biểu giá của chủ khác; driver không có quyền sửa.

Form đang nối API thật chỉ cấu hình một giá điện cho toàn ngày. Hai template
trong `frontend/templates/tariffs/` từ VY-TU còn là mock và chưa có route `/tariffs`;
không dùng chúng làm bằng chứng lưu biểu giá nhiều khung thành công.

## 6. Bắt đầu phiên qua OCPP với trụ giả lập — T-51/T-52/SCRUM-194

Ở đây kiểm thử tin nhắn OCPP và phiên trong database bằng simulator, không có
thiết bị sạc hoặc điện năng vật lý. `/stations` là danh sách trạm; chữ **Chỉ xem**
trong bảng nói về quyền quản lý trạm, không phải nút bắt đầu phiên.

1. Đăng nhập driver. Bấm **Bắt đầu sạc** ở menu trái, hoặc **Chọn trụ để sạc**
   trên trang **Trạm sạc**. Cả hai mở <http://localhost:8000/monitoring>.
2. Tìm `CP_VINCOM_01`, bấm vào **tên Trạm sạc Vincom Center** ở đầu thẻ trạm để mở bảng bên phải.
   Tìm phần trụ `CP_VINCOM_01` trong bảng này. Nếu dùng Docker chưa bật trụ demo,
   có thể dùng `SIM-01` online để thử mục 6–8; muốn thử giá Vincom ở mục 9 thì cần
   bật trụ demo như mục 0. Trụ phải online và đầu nối phải Available.
3. Trong phần trụ đó, chọn đầu nối Available và nhập mã RFID của driver demo, thường là
   `DEMO-DRIVER-0005` trên DB seed chuẩn. Nếu DB khác, dùng mã đã cấp trong `id_tags`.
4. Bấm **Bắt đầu sạc** một lần. Nút khóa trong lúc chờ, tối đa 60 giây.
5. Simulator nhận lệnh và gửi StartTransaction. Chỉ khi backend có phiên thực,
   giao diện mới báo bắt đầu thành công và đưa driver về `/sessions/mine`.
6. Ghi lại mã phiên `#...` và mã trụ để dừng đúng phiên ở mục 8.
7. Mở chi tiết, đóng rồi mở lại trong lúc chờ: không phát sinh lệnh trùng.
8. Đầu nối bận/lỗi/bảo trì/offline không chọn để bắt đầu.
9. Ca Rejected/timeout/disconnect có test tự động; fleet mặc định thường trả
   Accepted nên không đủ để tự tạo mọi ca lỗi này bằng thao tác bấm trên web.

Mã thẻ sai có thể khiến lệnh remote được nhận nhưng StartTransaction bị từ chối;
không coi thông báo Accepted của lệnh là một phiên đã bắt đầu.

## 7. Phiên hiện tại và lịch sử tài xế — T-47/T-48

1. Driver vào `/sessions/mine` sau mục 6: thấy đúng trụ, đầu nối, thời điểm bắt đầu.
2. F5 không tạo phiên mới và không tăng kWh giả.
3. Driver chỉ xem phiên của mình; API phiên của tài xế khác bị chặn.
4. Khi chưa có phiên đang chạy, `/api/sessions/current` trả 204 là hợp lệ.

Fleet hiện không tự phát MeterValues đều đặn cho phiên remote. kWh lúc đang sạc
có thể giữ 0; đây chưa phải bằng chứng chức năng cập nhật số đo liên tục đạt.

## 8. Dừng từ xa và tính kWh — T-49/T-50/T-39

**Tài khoản tài xế không có nút Dừng từ xa.** Theo S-23/T-50, nút này chỉ hiện
cho admin/operator trên trang **Phiên sạc**, khi phiên còn đang sạc. Nó nằm ở
cột **Thao tác** của bảng (hoặc thẻ phiên đang sạc phía trên), không nằm trong
hộp **Chi tiết phiên sạc**.

1. Đăng xuất driver rồi đăng nhập `operator@csms.local` / `Operator@2024!`, hoặc
   dùng cửa sổ riêng tư để giữ phiên đăng nhập driver ở cửa sổ cũ. Hai tab thường
   cùng trình duyệt dùng chung cookie nên không giữ hai vai trò độc lập.
2. Bấm menu **Phiên sạc**, mở <http://localhost:8000/sessions>. Tìm đúng mã phiên
   và mã trụ đã ghi ở mục 6, trạng thái **Đang sạc**.
3. Bấm **Dừng từ xa** ngay trên dòng đó, rồi **Xác nhận dừng sạc** trong hộp xác nhận.
   Simulator nhận RemoteStopTransaction và gửi StopTransaction.
4. Phiên có giờ kết thúc, trạng thái **Hoàn thành** (`completed`), lý do `Remote`;
   đầu nối về Available. Bấm vào mã phiên `#...` để xem điện năng và lý do kết thúc.
5. Simulator hiện dùng meterStart=1000 Wh và meterStop=2500 Wh,
   nên phiên thử này phải có **1,5 kWh**.
   Công thức: `(2500 − 1000) / 1000 = 1,5 kWh`; đây là số đo giả lập, không tăng
   theo thời gian chờ. Trong lúc sạc, kWh có thể vẫn bằng 0 như giới hạn ở mục 7.
6. Phiên đã đóng không còn nút dừng. API gửi lại lệnh dừng phải bị chặn, không tạo
   thêm hóa đơn hoặc trừ ví lần nữa.
7. Làm mới lịch sử driver: phiên đã kết thúc xuất hiện đúng người.

Ca StopTransaction đến muộn, số đo lùi, gửi trùng và khớp phiên sau nối lại nằm
trong các test OCPP/phiên; kiểm tra riêng bằng lệnh ở mục 14.

## 9. Hóa đơn và trừ ví — SCRUM-204/205/SCRUM-71

1. Mở hóa đơn phiên Vincom ở mục 8. Nếu đã tạo biểu giá 4000, phí 0 ở mục 5 trước
   lúc bắt đầu, tổng điện phải là **1,5 × 4000 = 6000 đồng**.
   Nếu chưa đổi giá, dùng đơn giá trong chi tiết hóa đơn để tính: ví dụ biểu giá
   thấp điểm hiện có 3000 đồng/kWh cho ra **4500 đồng**, không phải 6000 đồng.
2. Hóa đơn có khoảng thời gian, kWh, đơn giá, thành tiền và quy tắc làm tròn.
3. Ví driver có đúng một dòng trừ 6000 cho phiên đó; tải lại không trừ thêm.
4. Đổi giá mới rồi mở lại hóa đơn cũ: hóa đơn cũ giữ số tiền và snapshot cũ.
5. Kiểm thử cắt mốc cao điểm/nửa đêm bằng bảng đáp án độc lập SCRUM-65:

```powershell
Push-Location backend
try { ..\.venv\Scripts\python.exe -m pytest tests/unit/test_scrum65_pricing.py -q -rs }
finally { Pop-Location }
```

Hiện có 5 ca bị skip: 4 ca phí chiếm trụ chưa nối adapter kiểm thử và 1 ca đổi
phiên bản giá qua ngày. Không ghi 5 ca này là PASS. Bộ tính tiền của phiên hiện
chọn biểu giá tại lúc bắt đầu; chưa nghiệm thu đổi phiên bản giá giữa phiên.

## 10. Nạp tay và lịch sử ví — S-36/S-40

1. Admin mở `/wallet` (trang quản lý tài xế), chọn driver demo và ghi số dư trước.
2. Nạp tay 50000, mã phiếu `QA-20261009-001`: số dư tăng đúng 50000.
3. Nạp lại cùng mã phiếu: HTTP 409, số dư không tăng lần hai.
4. Driver mở `/wallet`: xem đúng số dư, lịch sử và liên kết hóa đơn của mình.
5. Accountant được xem theo quyền, không được nạp tay; driver không xem ví khác.

## 11. Nạp sandbox qua API — SCRUM-69

Frontend chưa nối nút checkout. Dùng PowerShell ở terminal thứ hai, hoặc `/docs`
sau khi đăng nhập driver. Đo số dư ngay trước và sau bước thanh toán:

```powershell
$qaBase = 'http://localhost:8000'
$qaLogin = @{email='driver@csms.local'; password='Driver@2024!'} | ConvertTo-Json
$null = Invoke-RestMethod "$qaBase/api/auth/login" -Method Post -ContentType 'application/json' -Body $qaLogin -SessionVariable qaDriver
$qaBefore = Invoke-RestMethod "$qaBase/api/wallet" -WebSession $qaDriver
$qaTopup = Invoke-RestMethod "$qaBase/api/wallet/topups/sandbox" -Method Post -WebSession $qaDriver -ContentType 'application/json' -Body '{"amount_vnd":50000}'
$qaTopup
# Pending: số dư chưa tăng. Chỉ là mô phỏng cổng thanh toán trên DB local.
$qaBody = @{order_code=$qaTopup.order_code; status='success'} | ConvertTo-Json
Invoke-RestMethod "$qaBase/api/wallet/topups/sandbox/simulate-pay" -Method Post -WebSession $qaDriver -ContentType 'application/json' -Body $qaBody
Invoke-RestMethod "$qaBase/api/wallet/topups/sandbox/simulate-pay" -Method Post -WebSession $qaDriver -ContentType 'application/json' -Body $qaBody
$qaAfter = Invoke-RestMethod "$qaBase/api/wallet" -WebSession $qaDriver
$qaBefore
$qaAfter
```

Mong đợi: lần đầu tăng 50000, gửi lại không cộng thêm. Lặp với một order khác,
status `failed`/`cancelled`: số dư không đổi. Nạp 9999 hoặc trên 10000000 bị 422.
Giao dịch của người khác không được tài xế thanh toán.

Giới hạn thực tế: `payment_url` trỏ tới checkout chưa có trang; webhook public
đã có trường signature nhưng chưa kiểm chữ ký. Vì vậy chưa nghiệm thu AC cổng
thanh toán/chữ ký thật và không đánh dấu toàn bộ SCRUM-69 Done.

## 12. API cấu hình trụ — SCRUM-60

Operator/admin mở `/docs`:

1. `PUT /api/charge-points/SIM-01/configuration/HeartbeatInterval`, body
   `{"value":1}`: 422 (hợp lệ là 30–3600 giây).
2. Khóa lạ bị 422. MeterValueSampleInterval hợp lệ là 5–900 giây.
3. Driver/owner bị 403. Trụ offline không được ghi cấu hình như đã áp dụng.
4. Với client OCPP hỗ trợ ChangeConfiguration/GetConfiguration, thử value=600,
   đọc lại và kiểm tra Accepted/RebootRequired; chỉ xác nhận reboot theo ý người dùng.

Fleet SimpleSimulator hiện chưa xử lý hai lệnh này, nên ca giá trị hợp lệ có thể
trả CALLERROR/502. Các ca Accepted/RebootRequired có unit test, chưa đủ bằng chứng
thành công qua fleet mặc định. Không coi bước 4 đã đạt nếu chưa có client hỗ trợ.

## 13. Nhật ký, bất thường và đối chiếu kWh — T-53/T-54/T-57/T-58/SCRUM-183/184

1. Admin/operator mở `/audit`, lọc mã trụ và thời gian sau Reset/start/stop:
   thấy log thật đúng thao tác/người thực hiện; F5 không tạo log thao tác mới.
2. Mở `/sessions/anomalies`, lọc lý do/thời gian. Rỗng là hợp lệ nếu chưa phát
   sinh phiên bất thường; dữ liệu được gọi từ backend.
3. Mở `/sessions/kwh-reconciliation`, kiểm tra lọc và xuất CSV/Markdown.
   Phân biệt nguồn mẫu với kết quả một lượt 20 trụ thật bằng nhãn nguồn.
4. Chạy mục 14 để có báo cáo 20 trụ thật; kiểm tra từng phiên MATCH,
   không thiếu/trùng phiên và sai số kWh không vượt 0,001.

## 14. Kiểm tra tự động và CI Docker

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Push-Location backend
try {
    ..\.venv\Scripts\python.exe -m ruff check app tests alembic ../tests ../scripts
    ..\.venv\Scripts\python.exe -m mypy app
    ..\.venv\Scripts\python.exe -m pip_audit --local --progress-spinner off
    ..\.venv\Scripts\python.exe -m pytest tests ../tests --ignore=../tests/test_scrum182_20charger_scenario.py --tb=short -q
} finally { Pop-Location }
node --test tests/frontend_behavior.cjs
# Docker Desktop phải chạy. Runner tạo và dọn stack thử riêng, không dùng DB web.
.\.venv\Scripts\python.exe scripts/run_sprint3_ci.py
```

Báo cáo JSON/Markdown/JUnit nằm ở `outputs/sprint3-ci/`. Các test tự động và
kiểm thử web thủ công là hai nguồn bằng chứng riêng; ghi cả hai trước khi tạo PR.

## 15. Tự tạo PR vào main và giữ commit

Sau khi kiểm thử, chỉ stage file bạn thực sự muốn đưa vào PR. Hai thay đổi local
trong `huongdan` được giữ ngoài các commit đồng bộ, cần xem riêng bằng `git status`.

```powershell
git status
git log --graph --oneline --decorate origin/main..HEAD
git push -u origin codex/integration-all-branches-20261009
```

Trên GitHub chọn base=`main`, compare=`codex/integration-all-branches-20261009`.
Ghi các ca đã PASS, FAIL, SKIP và giới hạn ở trên trong mô tả PR.
Khi merge, chọn **Create a merge commit / Merge pull request** để giữ nguyên
mã commit và tác giả của các nhánh. Không chọn Squash hoặc Rebase and merge.
Nếu repo chỉ cho squash/rebase, cần bật Allow merge commits trước khi merge.
Đợi check Sprint 3 CI của PR và xử lý các lỗi kiểm thử thủ công trước khi nhập main.
