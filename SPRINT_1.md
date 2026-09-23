# SPRINT 1 — Kế hoạch triển khai chi tiết

> **Sprint Goal**: Chủ trạm khai báo được trạm và trụ trên môi trường staging chạy thật
>
> **Capacity**: 12 SP | **Đã xếp**: 12 SP | **Độ dài**: 1 tuần (5 ngày làm việc)

---

## Tổng quan kiến trúc

```
TTCS_K8S4_N5/
├── hardware/                 # BACKEND — FastAPI (Python)
│   ├── app/
│   │   ├── main.py           # Khởi tạo FastAPI, mount router, lifespan
│   │   ├── config.py         # Đọc biến môi trường (pydantic Settings) — nơi DUY NHẤT đọc os.environ
│   │   ├── database.py       # Engine, session, Base
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── user.py       # users, roles, user_roles
│   │   │   ├── station.py    # stations
│   │   │   └── charge_point.py # charge_points, connectors
│   │   ├── schemas/          # Pydantic request/response
│   │   │   ├── user.py
│   │   │   ├── station.py
│   │   │   └── charge_point.py
│   │   ├── routers/          # REST endpoints
│   │   │   ├── auth.py       # S-02: đăng nhập, khoá tạm
│   │   │   ├── stations.py   # S-04: CRUD trạm
│   │   │   └── charge_points.py # S-05: thêm trụ/đầu nối
│   │   ├── services/
│   │   │   └── ownership.py  # Hàm lọc sở hữu dùng chung (T-07)
│   │   ├── core/
│   │   │   ├── security.py   # argon2id hash, cookie httpOnly
│   │   │   ├── deps.py       # FastAPI Depends: current_user, require_role(...)
│   │   │   └── logging.py    # Cấu hình log
│   │   └── tests/
│   │       └── unit/         # Test cho Sprint 1
│   ├── alembic/              # Migrations
│   │   └── versions/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pytest.ini
├── giaodien/                 # FRONTEND — HTML/CSS/JS thuần
│   ├── templates/
│   │   ├── base.html         # Layout gốc
│   │   ├── auth/
│   │   │   └── login.html    # Form đăng nhập (T-05)
│   │   └── stations/
│   │       ├── list.html     # Danh sách trạm (T-09)
│   │       └── form.html     # Form tạo/sửa trạm
│   └── static/
│       ├── css/
│       │   ├── base.css      # Biến màu, spacing, typography
│       │   └── components.css # Form, nút, bảng — tái sử dụng
│       └── js/
│           ├── api_client.js  # Mọi lời gọi API đi qua đây
│           └── form_guard.js  # Chặn bấm lưu 2 lần
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml  # Pipeline CI (T-02)
```

---

## Stories & Tasks chi tiết

---

### S-01: Khung ứng dụng chạy được trên staging (3 SP)

**User Story**: Là thành viên phát triển, tôi muốn có khung ứng dụng chạy được trên staging để mọi người bắt đầu viết code trên cùng một nền.

**NFR**: Bí mật nạp từ biến môi trường; log không in chuỗi kết nối cơ sở dữ liệu.

#### T-01: Dựng khung dự án và kết nối cơ sở dữ liệu

|                     |                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Khởi tạo dự án, cấu hình kết nối SQLite, chạy được migration đầu tiên. Viết `docker-compose.yml` để chạy ứng dụng (CSDL SQLite lưu dưới dạng file cục bộ). Migration này là mẫu đặt tên bảng và cột cho mọi migration sau — đặt tên theo `snake_case`, khoá chính `id`, cột thời gian `created_at`/`updated_at`. |
| **AC**        | Chạy`docker compose up` rồi khởi động ứng dụng thì kết nối được cơ sở dữ liệu, migration chạy sạch và chạy lùi được                                                                                                                                                                                                                                         |
| **NFR**       | Chuỗi kết nối đọc từ biến môi trường                                                                                                                                                                                                                                                                                                                                         |
| **Deps**      | không                                                                                                                                                                                                                                                                                                                                                                                 |
| **File tạo** | `docker-compose.yml`, `.env.example`, `hardware/Dockerfile`, `hardware/requirements.txt`, `hardware/app/main.py`, `hardware/app/config.py`, `hardware/app/database.py`, `hardware/alembic/`, `hardware/pytest.ini`                                                                                                                                                   |

**Hướng triển khai:**

1. Tạo `hardware/app/config.py` — dùng `pydantic-settings` đọc `DATABASE_URL`, `SECRET_KEY` từ env
2. Tạo `hardware/app/database.py` — SQLAlchemy async engine + session maker + Base
3. Tạo `hardware/app/main.py` — FastAPI app với lifespan quản lý DB connection
4. Tạo `hardware/Dockerfile` — multi-stage build Python 3.11+
5. Tạo `docker-compose.yml` — chỉ cần service `app` (SQLite là file local)
6. Init Alembic, tạo migration đầu tiên (bảng health check)
7. Tạo `.env.example` với mẫu biến cần thiết

#### T-02: Pipeline CI chạy build, lint, test

| Hạng mục          | Chi tiết                                                                                                                                          |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Cấu hình CI chạy build, lint, test trên mỗi push và mỗi pull request. Tạo sẵn một test đơn vị rỗng làm chỗ cho test sau bám vào. |
| **AC**        | Push commit cố ý sai lint thì pipeline đỏ và chặn merge; commit sạch thì xanh dưới 5 phút                                              |
| **NFR**       | Pipeline chạy xong dưới 5 phút                                                                                                                 |
| **Deps**      | T-01                                                                                                                                               |
| **File tạo** | `.github/workflows/ci.yml`, `hardware/app/tests/__init__.py`, `hardware/app/tests/unit/test_placeholder.py`                                  |

#### T-03: Triển khai tự động lên staging bằng Docker

| Hạng mục          | Chi tiết                                                                                                                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Đóng gói ứng dụng thành image, đẩy lên máy chủ riêng, chạy bằng Docker. Nối vào pipeline ở T-02 sau bước test. Viết bước kiểm sức khoẻ: gọi trang chủ, không trả 200 thì giữ container cũ. |
| **AC**        | Merge vào nhánh chính thì staging chạy phiên bản mới trong 10 phút, không cần thao tác tay; triển khai hỏng thì phiên bản cũ còn nguyên                                                                |
| **NFR**       | Triển khai thất bại thì giữ nguyên phiên bản cũ                                                                                                                                                                   |
| **Deps**      | T-02                                                                                                                                                                                                                       |
| **File tạo** | `.github/workflows/deploy.yml`, health check endpoint trong `main.py`                                                                                                                                                  |

---

### S-02: Đăng nhập bằng email và mật khẩu, khoá tạm khi sai nhiều lần (2 SP)

**User Story**: Là người dùng, tôi muốn đăng nhập bằng email và mật khẩu để vào được các chức năng phù hợp vai trò.

**NFR**: Mật khẩu hash bằng argon2id; đếm lần sai theo tài khoản và theo IP.

**SSD tham chiếu**: SSD-1 (xem `03_SSD_SPEC.md`)

#### T-04: Bảng `users`, `roles` kèm migration và seed năm vai trò

| Hạng mục          | Chi tiết                                                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Mô tả**   | Thêm bảng`users`, `roles`, bảng nối `user_roles`. Seed sẵn năm vai trò: tài xế, chủ trạm, vận hành viên, kế toán, quản trị. Đặt tên cột theo mẫu migration ở T-01. |
| **AC**        | Migration tiến và lùi được;`users.email` có ràng buộc unique; sau seed có đúng năm dòng trong `roles`                                                                          |
| **NFR**       | Cột mật khẩu đủ dài cho hash argon2id                                                                                                                                                      |
| **Deps**      | T-01                                                                                                                                                                                             |
| **File tạo** | `hardware/app/models/user.py`, `hardware/alembic/versions/xxx_create_users_roles.py`                                                                                                         |

**Schema bảng `users`:**

```
users:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  email           VARCHAR(255) UNIQUE NOT NULL
  password_hash   VARCHAR(512) NOT NULL     -- argon2id hash
  full_name       VARCHAR(255) NOT NULL
  is_active       BOOLEAN DEFAULT TRUE
  failed_login_count  INTEGER DEFAULT 0
  locked_until    TIMESTAMP NULL
  last_failed_ip  VARCHAR(45) NULL
  created_at      TIMESTAMP DEFAULT NOW()
  updated_at      TIMESTAMP DEFAULT NOW()
```

**Schema bảng `roles`:**

```
roles:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  name            VARCHAR(50) UNIQUE NOT NULL  -- driver, station_owner, operator, accountant, admin
  created_at      TIMESTAMP DEFAULT NOW()

user_roles:
  user_id         FK -> users.id
  role_id         FK -> roles.id
  PRIMARY KEY (user_id, role_id)
```

**Seed 5 vai trò:** `driver`, `station_owner`, `operator`, `accountant`, `admin`

#### T-05: Form đăng nhập, tạo phiên, đếm lần sai và khoá tạm

| Hạng mục          | Chi tiết                                                                                                                                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Form đăng nhập, kiểm tra thông tin, tạo phiên đăng nhập bằng cookie httpOnly. Lưu số lần sai và thời điểm khoá vào bảng`users`, không lưu trong bộ nhớ tiến trình. Bố cục form này là mẫu cho mọi form sau. |
| **AC**        | Đăng nhập đúng thì vào trang chính; sai 5 lần thì lần thứ 6 bị khoá 15 phút; khởi động lại ứng dụng thì khoá vẫn còn                                                                                                  |
| **NFR**       | Thông báo lỗi không tiết lộ email có tồn tại hay không                                                                                                                                                                               |
| **Deps**      | T-04                                                                                                                                                                                                                                           |
| **File tạo** | `hardware/app/routers/auth.py`, `hardware/app/schemas/user.py`, `hardware/app/core/security.py`, `giaodien/templates/auth/login.html`                                                                                                  |

**Ràng buộc từ SSD-1:**

- Đếm sai lưu ở DB (cột trên `users`), KHÔNG lưu biến trong tiến trình
- Thông báo lỗi sai mật khẩu và sai email phải **giống hệt nhau**: `"email hoặc mật khẩu không đúng"`
- Đã sai ≥5 lần liên tiếp → `"tài khoản tạm khoá 15 phút"` (dù lần này nhập đúng)
- Mọi API khác: phiên hết hạn → 401 + chuyển về trang đăng nhập

---

### S-03: Mỗi vai trò chỉ thấy và thao tác được phần việc của mình (2 SP)

**User Story**: Là quản trị viên, tôi muốn kiểm soát quyền truy cập theo vai trò để bảo vệ dữ liệu.

#### T-06: Middleware kiểm vai trò, mặc định từ chối route chưa khai quyền

| Hạng mục          | Chi tiết                                                                                                                                                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Một lớp middleware kiểm vai trò trước khi vào handler, thay vì rải lệnh`if` trong từng handler. Route khai báo vai trò được phép bằng một khai báo ngắn cạnh định nghĩa route; không khai thì chặn. |
| **AC**        | Gọi route chưa khai quyền bằng tài khoản quản trị vẫn nhận 403; khai quyền xong thì đúng vai trò mới qua được                                                                                                  |
| **NFR**       | Mặc định là từ chối — route mới không khai báo quyền thì bị chặn                                                                                                                                                    |
| **Deps**      | T-05                                                                                                                                                                                                                              |
| **File tạo** | `hardware/app/core/deps.py`                                                                                                                                                                                                     |

**Cách triển khai:**

```python
# Trong deps.py
def require_role(*roles: str):
    """FastAPI Dependency — inject vào route để kiểm vai trò"""
    async def checker(current_user = Depends(get_current_user)):
        if not any(r.name in roles for r in current_user.roles):
            raise HTTPException(403)
        return current_user
    return checker

# Trong router
@router.get("/stations", dependencies=[Depends(require_role("station_owner", "admin"))])
```

#### T-07: Lọc theo quyền sở hữu ở tầng truy vấn và test 403 bằng curl

| Hạng mục          | Chi tiết                                                                                                                                                                                          |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Viết hàm truy vấn dùng chung nhận tài khoản hiện tại và tự thêm điều kiện chủ sở hữu vào mọi truy vấn trạm. Viết test gọi API bằng hai tài khoản chủ trạm khác nhau. |
| **AC**        | Chủ trạm A gọi API trạm của B bằng curl nhận 403 và có một dòng nhật ký; test tự động phủ ca này                                                                                 |
| **NFR**       | Điều kiện sở hữu nằm trong một hàm duy nhất, không chép tay vào từng truy vấn                                                                                                        |
| **Deps**      | T-06                                                                                                                                                                                               |
| **File tạo** | `hardware/app/services/ownership.py`, `hardware/app/tests/unit/test_ownership.py`                                                                                                              |

---

### S-04: Chủ trạm tạo và sửa thông tin trạm sạc (2 SP)

**User Story**: Là chủ trạm, tôi muốn khai báo trạm sạc để quản lý tài sản của mình.

#### T-08: Bảng `stations` kèm migration và liên kết chủ sở hữu

| Hạng mục          | Chi tiết                                                                                                                              |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Thêm bảng`stations` có khoá ngoại tới `users` làm chủ sở hữu, cột trạng thái hoạt động, toạ độ kiểu số thực. |
| **AC**        | Migration tiến và lùi được; xoá tài khoản chủ trạm còn trạm thì bị chặn bởi khoá ngoại                              |
| **NFR**       | Có chỉ mục trên cột chủ sở hữu vì mọi truy vấn của chủ trạm lọc theo cột này                                          |
| **Deps**      | T-04                                                                                                                                   |
| **File tạo** | `hardware/app/models/station.py`, `hardware/alembic/versions/xxx_create_stations.py`                                               |

**Schema bảng `stations`:**

```
stations:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  name            VARCHAR(255) NOT NULL
  address         TEXT
  latitude        FLOAT
  longitude       FLOAT
  status          VARCHAR(20) DEFAULT 'active'   -- active, inactive, maintenance
  owner_id        FK -> users.id (INDEX)
  created_at      TIMESTAMP DEFAULT NOW()
  updated_at      TIMESTAMP DEFAULT NOW()
```

#### T-09: Màn hình tạo, sửa và danh sách trạm của chủ trạm

| Hạng mục          | Chi tiết                                                                                                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Form tạo/sửa trạm và danh sách trạm của tôi. Dùng lại bố cục form và cách hiện lỗi tại ô của form đăng nhập T-05. Danh sách gọi qua hàm truy vấn có lọc sở hữu ở T-07. |
| **AC**        | Tạo, sửa, xem danh sách trạm đều chạy; lỗi nhập liệu hiện ngay tại ô sai; nút lưu bị vô hiệu trong lúc đang gửi                                                                  |
| **NFR**       | Form gửi đi phải chặn bấm hai lần liên tiếp                                                                                                                                                   |
| **Deps**      | T-08                                                                                                                                                                                                  |
| **File tạo** | `hardware/app/routers/stations.py`, `hardware/app/schemas/station.py`, `giaodien/templates/stations/list.html`, `giaodien/templates/stations/form.html`                                       |

---

### S-05: Chủ trạm thêm trụ và đầu nối, mã trụ duy nhất (1 SP)

**User Story**: Là chủ trạm, tôi muốn thêm trụ sạc vào trạm để chuẩn bị kết nối OCPP.

#### T-10: Bảng `charge_points`, `connectors` kèm migration và ràng buộc unique

| Hạng mục          | Chi tiết                                                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Hai bảng con của`stations` theo quan hệ cha-con hai tầng. `charge_points.code` unique toàn hệ thống và có chỉ mục. |
| **AC**        | Migration tiến và lùi được; chèn hai trụ cùng`code` thì cơ sở dữ liệu từ chối                                   |
| **NFR**       | `connectors` có cột số thứ tự khớp với `connectorId` trong tin nhắn OCPP, bắt đầu từ 1                            |
| **Deps**      | T-08                                                                                                                              |
| **File tạo** | `hardware/app/models/charge_point.py`, `hardware/alembic/versions/xxx_create_charge_points.py`                                |

**Schema bảng `charge_points`:**

```
charge_points:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  code            VARCHAR(50) UNIQUE NOT NULL (INDEX)
  station_id      FK -> stations.id
  vendor          VARCHAR(255)
  model           VARCHAR(255)
  firmware_version VARCHAR(100)
  status          VARCHAR(20) DEFAULT 'offline'  -- online, offline
  last_seen_at    TIMESTAMP NULL
  created_at      TIMESTAMP DEFAULT NOW()
  updated_at      TIMESTAMP DEFAULT NOW()
```

**Schema bảng `connectors`:**

```
connectors:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  charge_point_id FK -> charge_points.id
  connector_id    INTEGER NOT NULL        -- bắt đầu từ 1, khớp OCPP connectorId
  status          VARCHAR(20) DEFAULT 'unavailable'
  error_code      VARCHAR(50) DEFAULT 'NoError'
  created_at      TIMESTAMP DEFAULT NOW()
  updated_at      TIMESTAMP DEFAULT NOW()
  UNIQUE (charge_point_id, connector_id)
```

#### T-11: Form thêm trụ kèm số đầu nối, chặn mã trùng ngay tại ô nhập

| Hạng mục          | Chi tiết                                                                                                                                       |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Form thêm trụ trong trang chi tiết trạm, kiểm mã trùng bằng một lời gọi API khi rời ô nhập, và kiểm lại ở máy chủ khi lưu. |
| **AC**        | Nhập mã đã có thì ô nhập báo đỏ trước khi bấm lưu; lách qua giao diện gửi thẳng API thì máy chủ vẫn từ chối            |
| **NFR**       | Không tin kết quả kiểm ở trình duyệt, máy chủ là nơi quyết                                                                          |
| **Deps**      | T-10                                                                                                                                            |
| **File tạo** | `hardware/app/routers/charge_points.py`, `hardware/app/schemas/charge_point.py`                                                             |

---

### K-01: Spike — Trụ sạc ảo nối WebSocket tối giản (2 SP)

| Hạng mục          | Chi tiết                                                                                                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mô tả**   | Tìm hiểu OCPP 1.6J, chọn simulator (mã nguồn mở hoặc tự viết). Đầu ra: script Python kết nối WebSocket tới server, gửi BootNotification, nhận response. |
| **File tạo** | `hardware/app/dev_tools/ocpp_simulator/simulator.py`, `hardware/app/dev_tools/ocpp_simulator/seed_codes.txt`                                                        |

> ⚠️ Simulator KHÔNG được import bất cứ gì từ `app/` và ngược lại.

---

## Thứ tự triển khai (dependency graph)

```
T-01 ──┬── T-02 ── T-03
       │
       └── T-04 ──┬── T-05 ── T-06 ── T-07
                   │
                   └── T-08 ──┬── T-09
                              │
                              └── T-10 ── T-11

K-01 (song song, không phụ thuộc)
```

**Ngày 1**: T-01 + K-01 (song song)
**Ngày 2**: T-02, T-04 (song song sau T-01)
**Ngày 3**: T-03, T-05, T-08 (song song)
**Ngày 4**: T-06, T-09, T-10
**Ngày 5**: T-07, T-11, tích hợp + test

---

## Definition of Done (Sprint 1)

- [ ] Code review đã duyệt bởi ít nhất một thành viên khác
- [ ] Unit test cho nhánh logic mới; độ phủ trên phần thay đổi không giảm
- [ ] CI xanh: build, lint, typecheck, test
- [ ] Không có secret trong mã nguồn; quét phụ thuộc sạch
- [ ] AC pass trên staging với trụ ảo chạy thật, không chỉ bằng test đơn vị
- [ ] Không log dữ liệu định danh cá nhân, mã thẻ, và không log thông tin thanh toán
- [ ] README cập nhật nếu đổi hành vi công khai hoặc thêm biến môi trường

---

## Quy tắc cứng cần nhớ

1. **Tiền lưu bằng số nguyên (đồng)**, không dùng số thực
2. **Mọi bí mật đọc từ `config.py`**, không hardcode, không rải `os.environ` khắp nơi
3. **Không tạo file**: `utils.py`, `helpers.py`, `common.py`
4. **Không log**: mật khẩu, token, mã thẻ đầy đủ, PII
5. **Mặc định từ chối** (deny-by-default) với mọi route chưa khai quyền
6. **Lọc sở hữu** chỉ ở `services/ownership.py` — không copy vào từng query
7. **Mỗi file tối đa ~250 dòng** (handler OCPP: ~150 dòng)
8. **Frontend**: mọi trang extends `base.html`, mọi API gọi qua `api_client.js`

---

## Biến môi trường cần thiết (.env.example)

```env
# Database
DATABASE_URL=sqlite:///./csms.db

# Security
SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60

# App
APP_ENV=development
LOG_LEVEL=INFO

# Login protection
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15
```

---

## Dependencies (requirements.txt)

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.23
alembic>=1.13.0
pydantic-settings>=2.1.0
argon2-cffi>=23.1.0
python-multipart>=0.0.6
jinja2>=3.1.2
itsdangerous>=2.1.2
httpx>=0.25.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
ruff>=0.1.0
```
