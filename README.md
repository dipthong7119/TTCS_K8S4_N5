# CSMS — Nền tảng vận hành trạm sạc xe điện

> **Nhóm**: TTCS_K8S4_N5 | **Sprint hiện tại**: Sprint 2

Hệ thống quản lý trạm sạc xe điện (Charging Station Management System) xây dựng bằng
**FastAPI** (backend) + **HTML/CSS/JS thuần** (frontend) + PostgreSQL trong Docker
hoặc SQLite khi chạy trực tiếp trên Windows.
Trụ sạc trong dự án là **phần mềm giả lập** OCPP 1.6J, không phải thiết bị phần cứng thật.

---

## 👥 Thành viên nhóm

| Vai trò | Thành viên |
|---|---|
| Scrum Master | Trịnh Thanh Tùng |
| Backend Developer | Ngô Quang Tùng, Nguyễn Lâm Tùng, Hoàng Văn Tân |
| Frontend Developer | Phạm Văn Tuấn, Vy Hoàng Tú, Đặng Ngọc Đại |
| Tester | Tạ Như Vinh, Hoàng Văn Đức |

---

## 🚀 Khởi chạy nhanh

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

## 🔑 Tài khoản đăng nhập demo

> ⚠️ Các tài khoản dưới đây dùng cho môi trường **phát triển / demo** cục bộ.
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
migration; ví dụ tài khoản seed đầu tiên thường có mã `DEMO-DRIVER-0005`.

Khi `APP_ENV=development`, lần khởi động đầu sẽ tự thêm các trạm/trụ/đầu nối còn
thiếu và hai phiên lịch sử mẫu cho tài xế. Phiên mẫu được đánh dấu trong giao diện;
không có chi phí mẫu vì dự án chưa cấu hình biểu giá. Admin, vận hành và kế toán
xem phiên toàn mạng; chủ trạm chỉ xem phiên thuộc trạm mình; tài xế chỉ xem phiên
của mình. Nhật ký kiểm toán chỉ dành cho admin và vận hành.

---

## 🗄️ Cơ sở dữ liệu

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

Đầu nối mới bắt đầu ở trạng thái `unavailable` cho tới khi nhận `StatusNotification`.
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

> **Quy tắc đặt tên migration**: `NNNN_mo_ta_ngan_gon.py`
> (ví dụ: `0004_add_charging_sessions.py`) — theo mẫu T-01 trong `prompts/SPRINT_1.md`.

---

## 📁 Cấu trúc thư mục

```
TTCS_K8S4_N5/
├── run.py                      ← Entry point chạy local (cạnh README này)
├── docker-compose.yml          ← Cấu hình Docker
├── .env                        ← Biến môi trường (KHÔNG commit)
├── .env.example                ← Mẫu biến môi trường (commit được)
├── README.md                   ← File này
│
├── backend/                    ← TOÀN BỘ Python / FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/           ← File migration (đặt tên NNNN_xxx.py)
│   └── app/
│       ├── main.py             ← Khởi tạo FastAPI + lifespan migration
│       ├── config.py           ← Nơi DUY NHẤT đọc biến môi trường
│       ├── database.py         ← Engine, session, Base
│       ├── models/             ← SQLAlchemy models (1 file = 1 nhóm bảng)
│       │   ├── user.py         ← users, roles, user_roles
│       │   ├── station.py      ← stations
│       │   └── charge_point.py ← charge_points, connectors
│       ├── schemas/            ← Pydantic request/response (sprint tiếp)
│       ├── routers/            ← REST endpoints (nhóm theo epic)
│       ├── services/           ← Logic nghiệp vụ thuần
│       └── tests/              ← Unit & integration tests
│
├── frontend/                   ← HTML / CSS / JS thuần
│   ├── templates/              ← Jinja2 templates
│   └── static/                 ← CSS, JS, ảnh tĩnh
│
├── prompts/                    ← Tài liệu quy chuẩn dự án
│   ├── 01_CODEBASE_MAP.md      ← Bản đồ thư mục (nguồn sự thật)
│   ├── 02_CODING_STANDARDS.md  ← Quy chuẩn code
│   ├── 03_SSD_SPEC.md          ← Đặc tả luồng nghiệp vụ
│   └── SPRINT_1.md             ← Kế hoạch Sprint 1 chi tiết
│
└── ketqua/                     ← Log kết quả từng task
```

---

## 🌿 Biến môi trường

Tất cả biến được định nghĩa trong `backend/app/config.py` — **không rải `os.environ` khắp nơi**.

| Biến | Mặc định | Mô tả |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./csms.db` | Chuỗi kết nối DB |
| `CSMS_DB_NAME` | `csms` | Tên database PostgreSQL dùng bởi Docker Compose |
| `CSMS_DB_USER` | `csms` | Tài khoản PostgreSQL dùng bởi Docker Compose |
| `CSMS_DB_PASSWORD` | `csms` | Mật khẩu PostgreSQL dùng bởi Docker Compose; đổi trước khi triển khai |
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

## ⚙️ CI/CD & Deploy

Pipeline GitHub Actions gồm 2 workflow:

| File | Kích hoạt | Tác vụ |
|---|---|---|
| `.github/workflows/ci.yml` | Mọi push / PR | Build, lint (ruff), test (pytest) |
| `.github/workflows/deploy.yml` | Merge vào `main` | Deploy lên staging server |

**Secrets cần cấu hình** tại `Settings > Secrets and variables > Actions`:

| Secret | Giá trị |
|---|---|
| `STAGING_HOST` | IP hoặc domain server staging |
| `STAGING_USERNAME` | Tên user SSH (vd: `ubuntu`) |
| `STAGING_SSH_KEY` | Private key SSH |
| `STAGING_SSH_PORT` | Cổng SSH (thường `22`) |
| `GHCR_PAT` | GitHub Personal Access Token |

---

## 📐 Quy tắc làm việc nhóm

1. **Trước khi tạo file mới** — tra `prompts/01_CODEBASE_MAP.md` xem file đó thuộc thư mục nào.
2. **Không hardcode bí mật** — mọi key/password đọc qua `config.py` từ biến môi trường.
3. **Không log** mật khẩu, token, mã thẻ đầy đủ, thông tin cá nhân (PII).
4. **Mỗi migration = 1 thay đổi schema rõ ràng**, có thể rollback (`downgrade`).
5. **Không tạo** `utils.py`, `helpers.py`, `common.py` — mọi hàm phải có module rõ ràng.
6. **Không commit** file `.env`, `csms.db`, `*.sqlite`.
7. **Tối đa ~250 dòng/file** backend; ~150 dòng/template HTML.
8. Ghi log kết quả mỗi task vào `ketqua/T-XX_ket_qua.md`.

