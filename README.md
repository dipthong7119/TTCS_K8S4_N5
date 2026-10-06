# CSMS — Nền tảng vận hành trạm sạc xe điện

> **Nhóm**: TTCS_K8S4_N5 | **Sprint hiện tại**: Sprint 3 — xem [phân công](huongdan/Phan_cong_Sprint3.md)

Hệ thống quản lý trạm sạc xe điện (Charging Station Management System) xây dựng bằng
**FastAPI** (backend) + **HTML/CSS/JS thuần** (frontend) + PostgreSQL trong Docker
hoặc SQLite khi chạy trực tiếp trên Windows.
Trụ sạc trong dự án là **phần mềm giả lập** OCPP 1.6J, không phải thiết bị phần cứng thật.

---

## Thành viên nhóm

| Vai trò | Thành viên |
|---|---|
| Scrum Master | Trịnh Thanh Tùng |
| Backend Developer | Ngô Quang Tùng, Nguyễn Lâm Tùng, Hoàng Văn Tân, Tạ Như Vinh, Hoàng Văn Đức |
| Frontend Developer | Phạm Văn Tuấn, Vy Hoàng Tú, Đặng Ngọc Đại |
| Kiểm thử / review | Các thành viên tự kiểm thử và review chéo theo phân công Sprint 3 |

---

## Khởi chạy nhanh

### Yêu cầu môi trường

| Công cụ | Phiên bản tối thiểu |
|---|---|
| Python | 3.11+ |
| Docker | 24+ |
| Docker Compose | 2.20+ |

Docker Compose chạy FastAPI cùng PostgreSQL 15 và lưu dữ liệu trong volume riêng.
`run.ps1` chạy trực tiếp trên Windows với SQLite tại `backend/csms.db`. Hai cách
dùng chung cổng `8000`, vì vậy chỉ chạy một cách tại một thời điểm.

### Chạy bằng Docker

PowerShell:

```powershell
Copy-Item .env.example .env   # chỉ cần lần đầu
docker compose up --build
```

Mở `http://localhost:8000/login`. Dừng bằng `Ctrl+C`; chạy nền thì dùng
`docker compose up --build -d`, và dừng bằng `docker compose down`. Lệnh `down`
giữ nguyên dữ liệu PostgreSQL trong volume `postgres_data`.
Docker Desktop/Engine phải đang chạy trước khi gọi Compose. Ứng dụng chờ PostgreSQL
sẵn sàng rồi tự chạy Alembic trước khi mở cổng HTTP.

### Chạy trụ OCPP ảo bằng Compose (T-55 / SCRUM-115)

Với `APP_ENV=development`, startup seed sẵn `SIM-01` đến `SIM-20` vào PostgreSQL.
Một container simulator chạy các client WebSocket riêng, gửi BootNotification,
StatusNotification và Heartbeat theo chu kỳ server trả về. Bật profile để chạy
**20 trụ** mặc định cùng ứng dụng:

```powershell
docker compose --profile ocpp-simulator up -d --build simulator
docker compose logs -f simulator
```

Đăng nhập tài khoản vận hành, mở `/monitoring` để xem 20 trụ online của
trạm thử nghiệm OCPP. Trang luôn lấy dữ liệu từ API. Profile chỉ chạy khi được bật.
Simulator báo trạng thái cho đủ hai đầu nối của mỗi trụ `SIM-*`.

Để thử cả 5 trụ mẫu tại Vincom, AEON và Thủ Thiêm, đặt
`CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS=true` trong `.env`, rồi chạy lại lệnh
Compose trên. Với count=20, tổng cộng **25 trụ / 49 đầu nối** kết nối thật qua
WebSocket. Các trụ mẫu dùng đúng số đầu nối 1–3 đã seed; `CP_AEON_FAULT` báo
`Faulted/GroundFailure`, `CP_DEMO_MAINT_01` báo `Unavailable` cho hai đầu nối.
Đây là trạng thái kiểm thử, được giữ sau Reset. Đặt lại `false` để chỉ chạy
nhóm `SIM-*`; `CSMS_SIMULATOR_COUNT` vẫn điều khiển riêng 1–20 mã SIM.

Muốn đổi số lượng hoặc server, đặt trong `.env` hoặc PowerShell trước khi chạy:

```powershell
$env:CSMS_SIMULATOR_COUNT = "3"
$env:CSMS_SIMULATOR_URL = "ws://app:8000/ocpp"
docker compose --profile ocpp-simulator up -d --build simulator
```

Số lượng hợp lệ **1–20**; chọn tuần tự từ `seed_codes.txt`, không sinh mã chưa
đăng ký. `app` là tên DNS nội bộ Compose. URL hỗ trợ `ws://`, `wss://` và đường
dẫn proxy tới endpoint OCPP; không chứa mật khẩu/token. Khi đổi server ngoài,
cần seed cùng các mã trên server đó. Môi trường production không tự seed mẫu.

Image simulator mặc định ghim `csms-simulator:1.0.0`. Khi cần dùng bản đã build
khác, đặt `CSMS_SIMULATOR_IMAGE=csms-simulator:<phiên-bản>` và chạy
`docker compose --profile ocpp-simulator up -d --no-build simulator`.
Dừng riêng trụ bằng `docker compose stop simulator`; nếu cấu hình sai hoặc một
client lỗi, container thoát lỗi để thấy trong log thay vì giữ một fleet thiếu trụ.
Lệnh chạy một trụ trực tiếp trước đây (`SIM-01 --host localhost --port 8000`)
vẫn được hỗ trợ. T-55 chỉ cung cấp dịch vụ trụ; kịch bản phiên ngắt–nối và gate CI
là T-46/T-56, thực hiện riêng theo phân công.

Hướng dẫn thử trực tiếp các luồng sau khi đồng bộ main:
[Kiểm thử web local](huongdan/kiem_thu_sau_pull_main.md).

### Kiểm thử giám sát và bộ lọc trụ trên web (T-24/T-25/T-35)

Trang `/monitoring` dùng một nguồn dữ liệu API/SSE từ các trụ OCPP ảo ở trên.
Bộ mẫu 20 trụ chạy riêng trên trình duyệt và nút chuyển nguồn đã được bỏ để
tránh hai bộ dữ liệu khác nhau. Simulator Docker và dữ liệu seed vẫn dùng
để kiểm thử qua backend khi không có phần cứng.

Bộ lọc áp dụng cho từng **trụ** trong trạm, cả dạng lưới, danh sách và ngăn chi tiết.
Với fleet 25 trụ, chọn **Lỗi** chỉ thấy `CP_AEON_FAULT`, không kéo theo
`CP_AEON_01`. Chọn **Tạm ngừng / Bảo trì** thấy `CP_DEMO_MAINT_01`.
`Unavailable` hiển thị tạm ngừng, tách khỏi `Faulted`; tổng lỗi đếm mỗi trụ
một lần dù nhiều đầu nối cùng báo lỗi. Các ô tổng vẫn thống kê toàn bộ dữ liệu.
Tìm mã trụ chỉ hiện trụ khớp; tìm tên/địa chỉ trạm có thể kết hợp bộ lọc trạng thái.

Đăng nhập bằng vai trò vận hành viên hoặc quản trị, mở chi tiết trạm rồi chọn
**Khởi động lại** trên một trụ online. Sau xác nhận Reset Soft/Hard, lệnh đi qua
backend tới simulator OCPP; trụ kết nối lại và báo trạng thái theo profile đã cấu hình.
Trụ lỗi và bảo trì vẫn giữ trạng thái kiểm thử sau Reset.

### Điều khiển phiên và đối chiếu kWh sau gộp HOANG-DUC

Nhánh f đã nhận API `POST /api/charge_points/{code}/remote-start` (T-51 /
SCRUM-193), cải tiến xử lý lỗi dừng phiên T-49 và công cụ đối chiếu kWh
SCRUM-183. Hợp đồng API ở [T-51](ketqua/T-51_hop_dong_api.md) và
[T-49](ketqua/T-49_hop_dong_api.md); cách thử và giới hạn hiện tại ở
[hướng dẫn web local](huongdan/kiem_thu_sau_pull_main.md).

Nút Bắt đầu sạc trên web vẫn là giao diện thử; simulator fleet chưa xử lý
RemoteStart/RemoteStop. Công cụ đối chiếu nhận hai tập dữ liệu đầu vào,
chưa tự thu thập kết quả 20 trụ. JSON mẫu phục vụ kiểm thử định dạng.

### Sao lưu và khôi phục PostgreSQL

Compose khởi chạy dịch vụ `backup`, tạo một bản sao lưu ngay khi dịch vụ bắt đầu,
sau đó lặp lại mỗi 24 giờ. Dump ở định dạng PostgreSQL custom được kiểm tra bằng
`pg_restore --list` trước khi lưu thành công trong volume Docker `postgres_backups`.
Không tạo thư mục `backups/` trong dự án. Xem danh sách dump bằng:

```powershell
docker compose run --rm --no-deps --entrypoint ls backup -lh /backups
```

Mặc định giữ 14 ngày; có thể đổi bằng `CSMS_BACKUP_RETENTION_DAYS` trong `.env`.

Để khôi phục, dừng ứng dụng và bộ lập lịch backup, rồi chạy lệnh sau trong
PowerShell, thay tên file bằng dump muốn dùng:

```powershell
docker compose stop app backup
docker compose run --rm --no-deps backup restore /backups/csms-20261003T020000Z.dump
```

Lệnh restore kiểm tra dump và yêu cầu nhập `RESTORE` trước khi ghi đè các đối
tượng tương ứng trong database. Sau đó khởi động lại ứng dụng và bộ backup:

```powershell
docker compose up -d app backup
```

Các file dump nằm trong volume Docker, ngoài thư mục mã nguồn và Git.
`docker compose down` giữ các volume dữ liệu và bản sao; `down -v` xoá chúng.

### Chạy bằng `run.ps1` trên Windows

```powershell
.\run.ps1
```

Lần đầu script tạo `.venv`, cài thư viện, lấy `.env` từ `.env.example` nếu chưa có,
chạy Alembic rồi khởi động server. Tắt bằng `Ctrl+C`; ứng dụng thoát gọn không in
traceback `KeyboardInterrupt`.

Không chép thư mục `.venv` giữa các máy vì virtualenv lưu đường dẫn Python của máy
tạo ra nó. Nếu `.venv` được chép hoặc Python gốc không còn ở đúng đường dẫn,
`run.ps1` sẽ phát hiện và tạo lại môi trường bằng `py -3` (Python Launcher).
Máy cần Python 3.11 trở lên và kết nối Internet để cài các thư viện ở lần chạy đầu.
Không cần chạy `Activate.ps1` hoặc `deactivate`; cứ chạy `.\run.ps1`, kể cả khi
VS Code đã tự kích hoạt và terminal đang hiện `(.venv)`. Đây chỉ là trạng thái của
terminal; `run.ps1` tự gọi Python trong `.venv`. Sau `Ctrl+C`, terminal giữ nguyên
trạng thái hiện tại, bạn có thể chạy lại `.\run.ps1` mà không cần `deactivate`.
Nếu muốn VS Code ngừng tự kích hoạt môi trường cho terminal, đổi thiết lập người
dùng `python-envs.terminal.autoActivationType` thành `off` rồi mở terminal mới;
thiết lập này có thể ảnh hưởng các dự án khác trong VS Code.

Khi dùng macOS/Linux hoặc muốn chạy thủ công, cài `backend/requirements.txt`, chạy
`alembic upgrade head` trong `backend/`, rồi chạy `python run.py` từ thư mục gốc.

### Chạy thủ công trên Windows (tùy chọn)

```powershell
# Chỉ cần lệnh này nếu .venv chưa có; nếu .venv chép từ máy khác, thêm --clear
py -3 -m venv .venv
# py -3 -m venv --clear .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt

Push-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location

.\.venv\Scripts\python.exe run.py
```

---

## Tài khoản đăng nhập demo

> Các tài khoản dưới đây dùng cho môi trường **phát triển / demo** cục bộ.
> **Không dùng trên môi trường production.**

| Vai trò | Email | Mật khẩu | Quyền truy cập |
|---|---|---|---|
| Quản trị viên | `admin@csms.local` | `Admin@2024!` | Toàn quyền hệ thống |
| Chủ trạm | `owner@csms.local` | `Owner@2024!` | Quản lý trạm, trụ sạc |
| Vận hành viên | `operator@csms.local` | `Operator@2024!` | Giám sát, dừng phiên từ xa |
| Kế toán | `accountant@csms.local` | `Accountant@2024!` | Xem báo cáo, lịch sử phiên |
| Tài xế | `driver@csms.local` | `Driver@2024!` | Xem lịch sử sạc của cá nhân |

> **Seed tài khoản**: Migration `0004_seed_demo_users` tạo sẵn năm tài khoản demo
> gắn với năm vai trò cho môi trường phát triển/demo. Không dùng tài khoản demo
> trên production.

Tài khoản tài xế demo được cấp thẻ giả lập `DEMO-DRIVER-<ID người dùng>` khi chạy
seed; ví dụ tài khoản seed đầu tiên thường có mã `DEMO-DRIVER-0005`.

Khi `APP_ENV=development`, lần khởi động đầu sẽ tự thêm các trạm/trụ/đầu nối còn
thiếu, phiên sạc, biểu giá, hóa đơn và giao dịch ví mẫu cho tài xế. Biểu giá demo
theo giờ TP.HCM là 3.000 VND/kWh (00:00–06:00, 22:00–24:00), 4.000 VND/kWh
(06:00–17:00), và 5.000 VND/kWh (17:00–22:00). Hóa đơn lưu bản chụp biểu giá;
chi phí được chia theo điện năng đo trong từng khung giờ. Giao dịch ví là sổ chỉ ghi
thêm; admin ghi nhận nạp thủ công kèm mã phiếu thu, kế toán chỉ xem, tài xế xem ví
của mình. Chưa kết nối cổng thanh toán hoặc áp dụng giá demo để thu tiền thật.
Admin, vận hành và kế toán xem phiên toàn mạng; chủ trạm chỉ xem phiên thuộc trạm
mình; tài xế chỉ xem phiên của mình. Nhật ký kiểm toán chỉ dành cho admin và vận hành.

---

## Cơ sở dữ liệu

### Các bảng hiện có

| Bảng | Migration | Mô tả |
|---|---|---|
| `roles` | `0001_create_users_roles` | 5 vai trò: driver, station_owner, operator, accountant, admin |
| `users` | `0001_create_users_roles` | Người dùng, hash argon2id, chống brute-force |
| `user_roles` | `0001_create_users_roles` | Bảng nối nhiều-nhiều user ↔ role |
| `stations` | `0002_create_stations` | Trạm sạc, liên kết chủ sở hữu, toạ độ GPS |
| `charge_points` | `0003_create_charge_points` | Trụ sạc, `code` UNIQUE + INDEX cho OCPP |
| `connectors` | `0003_create_charge_points` | Đầu nối, `connector_id` khớp OCPP (bắt đầu từ 1) |
| `login_ip_attempts` | `9f2c6a1b7d40` | Bộ đếm khóa đăng nhập theo IP, tách khỏi tài khoản người dùng |
| `connector_errors` | `8b30b78eea0a` | Nhật ký lỗi đầu nối, chỉ ghi thêm |
| `ocpp_messages` | `3c710c686e60`, `a6d2f891c104` | Chống xử lý trùng theo cặp mã trụ/mã tin nhắn |
| `id_tags` | `578e5d2ba886`, `c7aa03e59214` | Thẻ giả lập liên kết với tài xế, có trạng thái khoá và hạn dùng |
| `charging_sessions` | `e81f0a6b2c44` | Giao dịch OCPP bắt đầu/kết thúc, chỉ mục một phiên mở trên mỗi đầu nối |
| `meter_values` | `e81f0a6b2c44` | Số đo OCPP đã nhận diện, tra cứu theo phiên và thời điểm |
| `orphan_messages` | `e81f0a6b2c44` | StopTransaction/MeterValues chưa ghép được với phiên để đối chiếu |
| `audit_logs` | `e81f0a6b2c44` | Nhật ký thao tác chỉ ghi thêm, lọc theo trụ/người/thời gian |
| `station_tariffs`, `tariff_bands` | `20260928_wallet` | Biểu giá theo khung giờ, có thời điểm hiệu lực và múi giờ trạm |
| `charging_invoices` | `20260928_wallet` | Chi phí và phân bổ kWh theo khung giá, lưu cùng phiên sạc |
| `wallet_ledger` | `20260928_wallet` | Nạp/chi ví bằng VND nguyên, mã phiếu duy nhất và sổ chỉ ghi thêm |

Trạm mới bắt đầu ở trạng thái `inactive`; chủ trạm bật hoạt động sau khi khai báo xong.
Đầu nối mới bắt đầu ở trạng thái `unknown` cho tới khi nhận `StatusNotification`.
`OCPP_HEARTBEAT_INTERVAL_SECONDS` dùng chung cho BootNotification và phát hiện ngoại tuyến;
biến cũ `HEARTBEAT_INTERVAL` vẫn được hỗ trợ nếu biến mới chưa được cấu hình.
Đăng nhập trả trang chính theo vai trò; chủ trạm chỉ nhận danh sách dữ liệu thuộc sở hữu của mình.
Một tiến trình ứng dụng quản lý các kết nối OCPP trong bộ nhớ; chạy nhiều worker/replica
cần chuyển bộ quản lý kết nối sang thành phần dùng chung trước khi triển khai.

### Làm việc với Alembic

```bash
cd backend

# Xem trạng thái migration hiện tại
alembic current

# Tạo migration mới sau khi thêm model
alembic revision --autogenerate -m "mo_ta_ngan_gon"

# Chạy migration lên phiên bản mới nhất
alembic upgrade head

# Lùi lại 1 bước (rollback)
alembic downgrade -1

# Lùi về đầu (xoá toàn bộ schema)
alembic downgrade base
```

> Tạo migration trong `backend/alembic/versions/` với revision duy nhất và mô tả
> rõ nội dung. Giữ nguyên tên/revision đã chạy; xem `prompts/01_CODEBASE_MAP.md`.

---

## Cấu trúc thư mục

```
TTCS_K8S4_N5/
├── run.py                      ← Entry point chạy local (cạnh README này)
├── docker-compose.yml          ← Cấu hình Docker
├── docker-compose.override.yml ← Mount frontend local
├── docker-compose.acceptance.yml ← Stack nghiệm thu riêng
├── run.ps1                     ← Khởi chạy trên Windows
├── .env                        ← Biến môi trường (KHÔNG commit)
├── .env.example                ← Mẫu biến môi trường (commit được)
├── README.md                   ← File này
│
├── backend/                    ← TOÀN BỘ Python / FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── tests/                  ← Unit test backend, tách khỏi app
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/           ← Lịch sử migration, giữ revision đã chạy
│   └── app/
│       ├── main.py             ← Khởi tạo FastAPI + lifespan migration
│       ├── config.py           ← Nơi DUY NHẤT đọc biến môi trường
│       ├── database.py         ← Engine, session, Base
│       ├── models/             ← SQLAlchemy models (1 file = 1 nhóm bảng)
│       │   ├── user.py         ← users, roles, user_roles
│       │   ├── station.py      ← stations
│       │   └── charge_point.py ← charge_points, connectors
│       ├── schemas/            ← Pydantic request/response
│       ├── routers/            ← REST endpoints (nhóm theo epic)
│       ├── services/           ← Logic nghiệp vụ thuần
│       ├── ocpp/handlers/      ← Handler theo loại tin nhắn OCPP
│       └── dev_tools/ocpp_simulator/ ← Client OCPP độc lập và danh sách SIM- codes
│
├── frontend/                   ← HTML / CSS / JS thuần
│   ├── templates/              ← Jinja2 templates
│   └── static/                 ← CSS, JS, ảnh tĩnh
│
├── prompts/                    ← Tài liệu quy chuẩn dự án
│   ├── 00_QUY_TAC_AGENT.md     ← Quy tắc làm việc cho agent
│   ├── 01_CODEBASE_MAP.md      ← Bản đồ thư mục (nguồn sự thật)
│   ├── 02_DAC_TA_DU_AN.md      ← Đặc tả task/backlog và DoD
│   └── backend_qa_prompt.md   ← Prompt kiểm thử backend
│
├── tests/                      ← Test API/migration/mạng/Docker và hành vi frontend
├── huongdan/                   ← Hướng dẫn, phân công và kế hoạch
│   ├── git_clone_push.md       ← Hướng dẫn Git đã gom
│   ├── Phan_cong_Sprint3.md    ← Phân công và reviewer
│   ├── test_cases_duc_sprint2.md ← Kịch bản kiểm thử thủ công
│   └── *.xlsx                 ← Workbook backlog/tasks của dự án
└── ketqua/                     ← Báo cáo và bằng chứng từng task
```

---

## Biến môi trường

Tất cả biến được định nghĩa trong `backend/app/config.py` — **không rải `os.environ` khắp nơi**.

| Biến | Mặc định | Mô tả |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./csms.db` | Chuỗi kết nối DB |
| `CSMS_DB_NAME` | `csms` | Tên database PostgreSQL dùng bởi Docker Compose |
| `CSMS_DB_USER` | `csms` | Tài khoản PostgreSQL dùng bởi Docker Compose |
| `CSMS_DB_PASSWORD` | `csms` | Mật khẩu PostgreSQL dùng bởi Docker Compose; đổi trước khi triển khai |
| `CSMS_BACKUP_RETENTION_DAYS` | `14` | Số ngày giữ file backup PostgreSQL |
| `CSMS_SIMULATOR_COUNT` | `20` | Số client OCPP chạy đồng thời, 1–20 mã đã seed |
| `CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS` | `false` | Thêm 5 client mẫu ở Vincom/AEON/Thủ Thiêm; tổng 25 trụ khi count=20 |
| `CSMS_SIMULATOR_URL` | `ws://app:8000/ocpp` | URL cơ sở của server OCPP cho simulator |
| `CSMS_SIMULATOR_IMAGE` | `csms-simulator:1.0.0` (Compose chính) | Tag image simulator; stack nghiệm thu mặc định dùng image ứng dụng đang kiểm tra |
| `SECRET_KEY` | *(phải đổi)* | Khoá ký session/JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Thời gian hết hạn token |
| `APP_ENV` | `development` | Môi trường (`development`/`production`) |
| `LOG_LEVEL` | `INFO` | Mức độ log |
| `MAX_LOGIN_ATTEMPTS` | `5` | Số lần sai tối đa trước khi khoá |
| `LOCKOUT_DURATION_MINUTES` | `15` | Thời gian khoá tài khoản (phút) |
| `OCPP_HEARTBEAT_INTERVAL_SECONDS` | `300` | Chu kỳ nhịp tim gửi cho trụ |
| `OCPP_HEARTBEAT_MULTIPLIER` | `2` | Số chu kỳ trước khi coi là ngoại tuyến |
| `OCPP_MESSAGE_RETENTION_DAYS` | `7` | Thời gian lưu khóa chống trùng OCPP |
| `OCPP_REMOTE_CALL_TIMEOUT_SECONDS` | `30` | Thời gian chờ câu trả lời lệnh Reset |
| `SESSION_OFFLINE_GRACE_SECONDS` | `21600` | Thời gian trụ ngoại tuyến trước khi phiên thành bất thường (6 giờ) |
| `REMOTE_STOP_REVIEW_SECONDS` | `120` | Thời gian chờ StopTransaction sau lệnh dừng từ xa |

---

## CI/CD & Deploy

Pipeline GitHub Actions gồm 2 workflow:

| File | Kích hoạt | Tác vụ |
|---|---|---|
| `.github/workflows/ci.yml` | Mọi push / PR; chạy thủ công hoặc được CD gọi | Ruff, Mypy, audit phụ thuộc, pytest, JS, build Docker và nghiệm thu Compose/OCPP |
| `.github/workflows/deploy.yml` | Push vào `main`, `master`, `f` | Gọi toàn bộ CI; chỉ triển khai staging từ `main`/`master` sau khi kiểm tra đạt |

CD dùng lại workflow CI tại cùng commit, nên lỗi Docker/OCPP cũng chặn triển khai.
Kiểm tra trên các nhánh chạy độc lập; các lần triển khai cùng server được xếp
tuần tự và không hủy giữa chừng khi có push mới. Node.js được chọn phiên bản 22;
bước nghiệm thu có giới hạn 5 phút, thu log khi lỗi và luôn dọn stack test.

**Secrets cần cấu hình** tại `Settings > Secrets and variables > Actions`:

| Secret | Giá trị |
|---|---|
| `STAGING_HOST` | IP hoặc domain server staging |
| `STAGING_USERNAME` | Tên user SSH (vd: `ubuntu`) |
| `STAGING_SSH_KEY` | Private key SSH |
| `STAGING_SSH_PORT` | Cổng SSH (thường `22`) |
| `GHCR_PAT` | GitHub Personal Access Token |

Máy staging cần có `docker-compose.yml` của phiên bản này tại `/opt/csms-staging`
và file `.env` đã cấu hình. Workflow dùng `docker compose -f docker-compose.yml`
để lấy cả backend và frontend từ cùng image. Khi phát triển local,
`docker-compose.override.yml` được nạp tự động để mount thư mục frontend.

Image mới được kiểm tra `/health` và trang chủ trên cổng loopback `18000` trước
khi thay ứng dụng đang chạy. Nếu bước kiểm tra này lỗi, container cũ vẫn chạy;
nếu lỗi sau khi thay image, workflow phục hồi image trước đó khi có sẵn.

Typecheck chạy `python -m mypy app` theo `backend/pyproject.toml`, gồm cả thân hàm
chưa có annotation. Model ORM đang dùng `Column`/`declarative_base` được giữ tại
ranh giới động; test và simulator không nằm trong phạm vi typecheck này.
Quét phụ thuộc chạy `python -m pip_audit --local --progress-spinner off`;
CI nâng pip trước khi cài dependencies và dừng khi typecheck/audit thất bại.

Thư viện chạy ứng dụng nằm trong `backend/requirements.txt`; công cụ kiểm tra
nằm trong `backend/requirements-dev.txt`. Cài file dev khi phát triển/chạy test:
`python -m pip install -r backend/requirements-dev.txt`.
CI lưu `backend/coverage.xml` thành artifact và chạy kiểm thử hành vi JS bằng Node.
Unit test backend nằm tại `backend/tests`, test hệ thống tại `tests` ở gốc.
Từ thư mục `backend`, chạy đúng lệnh như CI:

```powershell
..\.venv\Scripts\python.exe -m pytest tests ../tests --tb=short -q
..\.venv\Scripts\python.exe -m ruff check app tests alembic ../tests
```

Image Docker chỉ cài thư viện chạy ứng dụng; CI nạp image vừa build để dùng lại
trong kiểm thử Compose, không build lần hai.

### Nghiệm thu Sprint 1–2 trên Docker/PostgreSQL

Bộ Compose nghiệm thu dùng project riêng, database tạm trong RAM và cổng localhost
được Docker chọn tự động. Nó không dùng `.env` hay volume dữ liệu của bộ ứng dụng.
Các tài khoản/cấu hình trong file nghiệm thu chỉ dành cho bộ test này.

```powershell
docker compose --env-file .env.example -p csms-sprint12-acceptance -f docker-compose.acceptance.yml up -d --build --wait db app
.\.venv\Scripts\python.exe -m pytest tests/sprint2_docker_acceptance.py -v -s
# Giữ 50 kết nối và một SSE subscriber trong 10 phút:
.\.venv\Scripts\python.exe -m pytest tests/sprint2_docker_acceptance.py -k 50_connections --sprint2-soak-seconds=600 -v -s
docker compose --env-file .env.example -p csms-sprint12-acceptance -f docker-compose.acceptance.yml down -v --remove-orphans
```

Bộ này chạy migration tiến/lùi và kiểm FK/unique trên schema PostgreSQL riêng,
chạy một client trong container báo giờ lệch 5 tiếng, và lặp dừng/bật container
simulator ba lần với Heartbeat 5 giây. Đây là kiểm chứng local; staging cần chạy
lại các AC trên máy chủ staging khi có môi trường đó.

---

## Quy tắc làm việc nhóm

1. **Trước khi tạo file mới** — tra `prompts/01_CODEBASE_MAP.md` xem file đó thuộc thư mục nào.
2. **Không hardcode bí mật** — mọi key/password đọc qua `config.py` từ biến môi trường.
3. **Không log** mật khẩu, token, mã thẻ đầy đủ, thông tin cá nhân (PII).
4. **Mỗi migration = 1 thay đổi schema rõ ràng**, có thể rollback (`downgrade`).
5. **Không tạo** `utils.py`, `helpers.py`, `common.py` — mọi hàm phải có module rõ ràng.
6. **Không commit** file `.env`, `csms.db`, `*.sqlite`.
7. **Tối đa ~250 dòng/file** backend; ~150 dòng/template HTML.
8. Ghi log kết quả mỗi task vào `ketqua/T-XX_ket_qua.md`.
