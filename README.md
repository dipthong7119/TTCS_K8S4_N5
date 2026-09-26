# CSMS — Nền tảng vận hành trạm sạc xe điện

> **Nhóm**: TTCS_K8S4_N5 | **Sprint hiện tại**: Sprint 1

Hệ thống quản lý trạm sạc xe điện (Charging Station Management System) xây dựng bằng
**FastAPI** (backend) + **HTML/CSS/JS thuần** (frontend) + **SQLite** (database phát triển).
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

### Chạy bằng Docker (khuyến nghị)

```bash
# 1. Clone dự án
git clone <url_repo>
cd TTCS_K8S4_N5

# 2. Tạo file cấu hình từ mẫu
cp .env.example .env

# 3. Tạo sẵn file database rỗng (QUAN TRỌNG: để Docker không tạo nhầm thành thư mục khi mount volume)
# Trên Windows PowerShell:
New-Item -ItemType File -Path backend/csms.db -Force
# Trên macOS / Linux:
touch backend/csms.db

# 4. Build và khởi chạy
docker compose up --build -d

# 5. Kiểm tra trạng thái
curl http://localhost:8000/health
```

> **Lưu ý**: Khi container khởi động, Alembic tự động chạy `upgrade head`
> để tạo toàn bộ bảng và seed dữ liệu — **không cần chạy migration thủ công**.

Ứng dụng sẽ chạy tại: **http://localhost:8000**

### Chạy tại local (không dùng Docker)

```bash
# 1. Tạo môi trường ảo
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Cài thư viện
pip install -r backend/requirements.txt

# 3. Chạy migration để tạo DB
cd backend
alembic upgrade head
cd ..

# 4. Khởi chạy server
python run.py
# hoặc
cd backend && uvicorn app.main:app --reload --port 8000
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

---

## 🗄️ Cơ sở dữ liệu

### Các bảng hiện có (Sprint 1)

| Bảng | Migration | Mô tả |
|---|---|---|
| `roles` | `0001_create_users_roles` | 5 vai trò: driver, station_owner, operator, accountant, admin |
| `users` | `0001_create_users_roles` | Người dùng, hash argon2id, chống brute-force |
| `user_roles` | `0001_create_users_roles` | Bảng nối nhiều-nhiều user ↔ role |
| `stations` | `0002_create_stations` | Trạm sạc, liên kết chủ sở hữu, toạ độ GPS |
| `charge_points` | `0003_create_charge_points` | Trụ sạc, `code` UNIQUE + INDEX cho OCPP |
| `connectors` | `0003_create_charge_points` | Đầu nối, `connector_id` khớp OCPP (bắt đầu từ 1) |
| `login_ip_attempts` | `9f2c6a1b7d40` | Bộ đếm khóa đăng nhập theo IP, tách khỏi tài khoản người dùng |

Đầu nối mới bắt đầu ở trạng thái `unknown` cho tới khi nhận `StatusNotification`.
Đăng nhập trả trang chính theo vai trò; chủ trạm chỉ nhận danh sách dữ liệu thuộc sở hữu của mình.

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
| `SECRET_KEY` | *(phải đổi)* | Khoá ký session/JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Thời gian hết hạn token |
| `APP_ENV` | `development` | Môi trường (`development`/`production`) |
| `LOG_LEVEL` | `INFO` | Mức độ log |
| `MAX_LOGIN_ATTEMPTS` | `5` | Số lần sai tối đa trước khi khoá |
| `LOCKOUT_DURATION_MINUTES` | `15` | Thời gian khoá tài khoản (phút) |

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

