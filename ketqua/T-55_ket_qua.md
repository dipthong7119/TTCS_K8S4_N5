# T-55 / SCRUM-115 — Dịch vụ trụ ảo cấu hình được

Ngày thực hiện: **06/10/2026**. Người được phân công: **Trịnh Thanh Tùng**.
Reviewer theo `huongdan/Phan_cong_Sprint3.md`: **Hoàng Văn Đức**.
Nguồn yêu cầu: S-26 / T-55 trong `prompts/02_DAC_TA_DU_AN.md` và phân công Sprint 3.

## Kết quả và phạm vi

**Đã hoàn thiện chức năng và đạt kiểm thử local của T-55.** Một dịch vụ Compose
chạy đồng thời số client OCPP được cấu hình, sử dụng mã đã seed và xuất hiện
online trong API giám sát. Lượt này chỉ làm T-55; chưa thực hiện T-56 / SCRUM-116,
SCRUM-185 hoặc kịch bản phiên ngắt–nối ngẫu nhiên của T-46.

Đặc tả gốc đặt T-46 trước T-55; phân công Sprint 3 mới yêu cầu T-55 làm nền tảng
ngày 1–2 để nhóm viết kịch bản. Thực hiện theo phân công mới của người dùng.

## Thay đổi

- `backend/app/dev_tools/ocpp_simulator/simulator.py`: CLI `--count` và
  `--server-url`; mỗi trụ có socket, mã tin nhắn, Heartbeat và pending calls riêng.
  Các client chạy đồng thời, huỷ và thu dọn toàn bộ khi một client thất bại.
- Đọc mã từ `seed_codes.txt` cạnh simulator; chọn tuần tự `SIM-01` đến `SIM-20`.
  Test đối chiếu danh sách này với seed server. Không import logic server hoặc
  đọc biến môi trường trong simulator; Compose truyền cấu hình qua CLI.
- Từ chối số lượng ngoài **1–20**, mã trùng/sai tiền tố, URL không phải WebSocket
  hoặc có credentials/query/fragment. Giữ lệnh một trụ `SIM-01 --host ... --port ...`.
- `docker-compose.yml`: profile `ocpp-simulator`, chờ app healthy,
  `CSMS_SIMULATOR_COUNT=20`, `CSMS_SIMULATOR_URL=ws://app:8000/ocpp` mặc định;
  image riêng ghim `csms-simulator:1.0.0`, đổi qua `CSMS_SIMULATOR_IMAGE`.
- `docker-compose.acceptance.yml`: nhận cùng tham số; mặc định dùng image app
  đang kiểm tra, hỗ trợ đổi riêng image simulator. Giữ database và cổng test riêng.
- `.env.example`, `app/config.py`: khai báo cấu hình tập trung để file `.env`
  dùng chung vẫn hợp lệ; không sửa `.env` thực tế hoặc schema database.
- Bổ sung kiểm thử vào hai file test hiện có. Workflow hiện tại tự chạy các ca
  kiểm tra Boot/Heartbeat T-55; chưa thêm gate đối chiếu phiên/kWh của T-56.

## Bằng chứng kiểm thử

Docker Engine **29.8.0**; image runtime **Python 3.11**; host test **Python 3.14.2**.
Stack `csms-t55-check` dùng PostgreSQL 15, dữ liệu tạm và cổng localhost ngẫu nhiên.
Đo từ lệnh khởi động simulator khi app/db đã healthy, lấy kết quả từ
`/api/monitoring/tree` sau đăng nhập, không dùng dữ liệu mẫu trên trình duyệt.

| Kiểm tra | Kết quả |
| --- | --- |
| Bộ Python toàn dự án | **321 passed**, 59,88s; coverage tổng 63% |
| Ruff | Đạt |
| Mypy | Đạt, 41 file |
| Build image ứng dụng và simulator | Đạt |
| Docker regression + T-55 | **8 passed**, 107,26s |
| Chạy lại T-55 với image riêng `csms-simulator:1.0.0` và kiểm bản ghi Heartbeat mới | **3 passed**, 38,53s |
| Cấu hình 1 trụ trên image riêng | Đúng 1 mã online sau **0,689s** |
| Cấu hình 3 trụ trên image riêng | Đúng 3 mã online sau **0,698s** |
| Cấu hình 20 trụ trên image riêng | Đúng 20 mã online sau **0,804s**, dưới 1 phút |
| Heartbeat của từng trụ | Có bản ghi mới cho đủ các mã được chọn, vẫn online sau chu kỳ 5s |
| Số container | Một container simulator; app/db giữ nguyên ID |
| Dữ liệu mã trụ | Không tạo thêm mã; 20 mã và ID đã seed giữ nguyên |
| Tham số không hợp lệ | `--count 21` thoát với code 2 trước khi kết nối |
| Hồi quy PostgreSQL/OCPP | 10 test migration; 50 socket + SSE; 3 chu kỳ stop/start; candidate lỗi giữ app cũ healthy đều đạt |

Image simulator được build bằng Compose chính:
`sha256:525f8f5311280642995ded7fd9d2d909dd40aebdcbe00baf1c1532b769c776ed`.

## Đồng bộ cấu trúc dự án

Đã cập nhật `prompts/01_CODEBASE_MAP.md`, README gốc và `frontend/README.md`
theo các thư mục hiện có: `ocpp/handlers`, services, models, simulator, script
backup, frontend theo trang, test hệ thống, CI/CD và báo cáo. Tham chiếu tới các
prompt cũ không còn tồn tại được sửa trong các README. Cây nguồn đã chia đúng
vai trò nên không chuyển file chạy ứng dụng hoặc đổi lịch sử migration.
Sau lượt T-55, việc sắp xếp thực tế đã chuyển unit test sang `backend/tests`,
phân công và workbook sang `huongdan`; xem `prompts/01_CODEBASE_MAP.md` hiện hành.
Cache, database, backup và bản sao plugin là dữ liệu local đã ignore.

## Chạy lại

Ứng dụng development cần file `.env` theo mẫu, Docker đang chạy. Khởi động
20 trụ với stack chính:

```powershell
docker compose --profile ocpp-simulator up -d --build simulator
docker compose logs -f simulator
```

Mở `/monitoring`, chọn **Dữ liệu máy chủ (API)**. Đổi `CSMS_SIMULATOR_COUNT`
hoặc `CSMS_SIMULATOR_URL` trong `.env` rồi chạy lại lệnh trên. Server ngoài hoặc
production phải có sẵn các mã tương ứng, vì production không tự seed mẫu.

Kiểm thử độc lập, từ thư mục gốc:

```powershell
$env:CSMS_IMAGE = "csms-app:t55-check"
docker build -f backend/Dockerfile -t csms-app:t55-check .
docker compose --env-file .env.example --profile ocpp-simulator build simulator
$env:CSMS_SIMULATOR_IMAGE = "csms-simulator:1.0.0"
docker compose --env-file .env.example -p csms-t55-check -f docker-compose.acceptance.yml up -d --no-build --wait db app
.\.venv\Scripts\python.exe -m pytest tests/sprint2_docker_acceptance.py --docker-project=csms-t55-check -k t55 -v -s
docker compose --env-file .env.example -p csms-t55-check -f docker-compose.acceptance.yml down -v --remove-orphans
Remove-Item Env:CSMS_IMAGE, Env:CSMS_SIMULATOR_IMAGE
```

## Giới hạn nghiệm thu

Đã kiểm chứng dữ liệu giám sát thật qua API; chưa nghiệm thu giao diện bằng thao
tác trực quan hoặc staging, chưa có review của Đức. Các kết quả này không xác
nhận Done toàn bộ S-26/Sprint 3. Stack test riêng đã được dọn; dữ liệu ứng dụng
hiện có và workbook Excel được giữ nguyên. Các file người dùng đã xoá trước lượt
này được giữ nguyên trạng thái xoá. Chưa commit/push các thay đổi của lượt này.

## Bổ sung theo ảnh giám sát: 25 trụ và đủ đầu nối

Ngày **06/10/2026**, người dùng yêu cầu kiểm thử cả các trụ ngoài nhóm SIM.
Trước bổ sung, 5 trụ mẫu chỉ được seed trong DB, chưa có client OCPP; client
SIM chỉ báo đầu nối 1 nên đầu nối 2 còn `unknown`.

- Thêm `--include-demo-stations true/false` và cấu hình tập trung
  `CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS` cho cả hai file Compose.
  Mặc định false giữ phép thử T-55 đúng 1–20 mã SIM; máy hiện đặt true trong `.env`.
  Chỉ đổi cờ cấu hình này trong `.env`, giữ các cấu hình và bí mật khác.
- Khi bật, thêm 5 client độc lập dùng đúng mã, vendor/model và số đầu nối đã seed.
  Simulator vẫn không import logic server hoặc đọc biến môi trường trực tiếp.
- SIM báo đủ đầu nối 1 và 2. Client cũ dùng mã ngoài nhóm seed vẫn mặc định
  một đầu nối, giữ cách chạy đơn trụ trước đây.
- Trụ lỗi và bảo trì giữ trạng thái mẫu sau Reset; không tạo trạng thái đang
  sạc khi chưa có phiên. Không mở rộng sang RemoteStart/RemoteStop hoặc T-56.

| Trụ | Đầu nối | Trạng thái gửi |
| --- | --- | --- |
| SIM-01..SIM-20 | 2 mỗi trụ | Available |
| CP_VINCOM_01 | 2 | Available |
| CP_VINCOM_02 | 1 | Available |
| CP_AEON_01 | 3 | Available |
| CP_AEON_FAULT | 1 | Faulted / GroundFailure |
| CP_DEMO_MAINT_01 | 2 | Unavailable |

API local xác nhận **25/25 trụ online, 49 đầu nối, 0 đầu nối unknown**.
SSE local trả **200 text/event-stream** và nhận ping sau 15 giây.
Kiểm thử Python toàn dự án: **362 passed**, 63,61 giây; thêm 12 ca simulator.
Ruff và Mypy đạt (43 file ứng dụng).

Kiểm thử Compose riêng với PostgreSQL thật: **4 passed**, 53,84 giây, gồm
nhóm 1/3/20 SIM và nhóm 25 trụ/49 đầu nối. Heartbeat có cho đủ 25 mã;
Reset Soft trụ AEON lỗi thành công rồi khôi phục đúng hồ sơ lỗi/bảo trì.
Mã trụ/ID trong DB giữ nguyên. Stack test riêng được dọn, stack local giữ chạy.

Chạy thêm toàn bộ kiểm thử Compose: **9 passed**, 120,56 giây. Gồm migration
PostgreSQL, lệch đồng hồ, 50 socket + SSE, 3 lần stop/start, candidate lỗi,
nhóm 1/3/20 SIM và nhóm 25 trụ. Ca 25 trụ cũng đạt khi DB có thêm 50 trụ tải lớn;
chỉ khởi chạy các mã mẫu đã đăng ký, không thay đổi ID/mã hoặc dữ liệu trụ tải.

Hướng dẫn web cập nhật tại `huongdan/kiem_thu_sau_pull_main.md`; chọn dữ liệu
máy chủ API và tải lại trang để thấy cấu hình mới.
