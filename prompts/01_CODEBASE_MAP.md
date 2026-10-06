# Codebase Map — Nền tảng vận hành trạm sạc xe điện (CSMS)

> Đây là **dự án web thuần**: FastAPI (Python) phía server + HTML/CSS/JS phía
> trình duyệt. Không có mạch điện tử, không có lập trình nhúng, không có
> firmware thật. "Trụ sạc" trong toàn bộ dự án là **phần mềm giả lập** (một
> script Python giả lập tin nhắn OCPP), không phải thiết bị vật lý.
>
> Cập nhật ngày **06/10/2026**, sau Sprint 1–2, T-55, main `bff0369`
> và gộp `origin/DANG-DAI` tại `34a9b4d` (merge local `55d58a7`).
> Tài liệu này là **nguồn sự thật duy nhất** về "file này đặt ở đâu". Khi vibe
> code (AI sinh code), luôn đọc file này trước để biết đặt code mới vào thư mục
> nào — không tự sáng tạo thư mục mới, không tạo file `_v2`, `_final`, `_copy`.

## 0. Ánh xạ với repo hiện tại

| Thư mục trong repo | Vai trò thực sự | Ghi chú |
| --- | --- | --- |
| `frontend/` | **Frontend** — HTML/CSS/JS thuần | Giao diện phía client hiển thị dựa trên Jinja2 template. Trước đây bị nhầm là `giaodien/`. |
| `backend/` | **Backend** — toàn bộ Python/FastAPI (REST API + WebSocket OCPP + job nền) | Logic server, giao tiếp CSDL, và giả lập thiết bị. Trước đây bị nhầm là `hardware/`. |
| `tests/` (root) | **Kiểm thử hệ thống** | Test API/migration/mạng/Docker và hành vi frontend. Unit test backend nằm tại `backend/tests/`. |
| `prompts/` | **Hướng dẫn AI (Prompts)** | Chứa các quy ước chuẩn để đảm bảo AI sinh code đúng chuẩn. |
| `ketqua/` | **Bằng chứng / báo cáo** | Kết quả từng task, trace OCPP và đối chiếu Sprint 1–2. Không chứa code chạy ứng dụng. |
| `huongdan/` | **Hướng dẫn và kế hoạch** | Hướng dẫn Git, phân công Sprint 3, workbook backlog/tasks và kịch bản test thủ công. |
| Docker volume `postgres_backups` | **Dữ liệu runtime** | Dump PostgreSQL nằm trong Docker; không tạo thư mục `backups/` trong mã nguồn. |
| `.github/workflows/` | **CI/CD** | `ci.yml` kiểm tra; `deploy.yml` triển khai. |

---

## 1. Cây thư mục tổng (mức gốc)

```
TTCS_K8S4_N5/
├── backend/                  # BACKEND — FastAPI, toàn bộ logic server (Python)
├── frontend/                 # FRONTEND — HTML/CSS/JS thuần
├── prompts/                  # Chứa các file định hướng, quy ước cho AI
├── tests/                    # Kiểm thử tự động toàn hệ thống
├── ketqua/                   # Lưu kết quả test, báo cáo
├── huongdan/                 # Hướng dẫn, phân công, Excel và kịch bản test thủ công
│   ├── git_clone_push.md
│   ├── Phan_cong_Sprint3.md
│   ├── test_cases_duc_sprint2.md
│   ├── kiem_thu_sau_pull_main.md # Thao tác thử các luồng trên web local
│   └── *.xlsx                # Workbook Nền tảng vận hành trạm sạc xe điện (CSMS)
├── .github/workflows/        # ci.yml và deploy.yml
├── docker-compose.yml        # app + PostgreSQL + backup + simulator theo profile
├── docker-compose.override.yml # Mount frontend cho phát triển local
├── docker-compose.acceptance.yml # Stack kiểm thử riêng, cổng ngẫu nhiên, DB tạm
├── .env / .env.example       # File cấu hình biến môi trường
├── .gitignore / .dockerignore # Loại dữ liệu local, cache và công cụ AI khỏi nguồn/build
├── run.py / run.ps1          # Khởi chạy local trên Windows với SQLite
└── README.md                 # Tài liệu mô tả dự án
```

Quy tắc cứng: **mọi thứ Python nghiệp vụ nằm trong `backend/`, mọi thứ tĩnh
(HTML/CSS/JS) nằm trong `frontend/`.**

---

## 2. `backend/` (= BACKEND) — chi tiết

Kiến trúc phân lớp chuẩn của FastAPI.

```
backend/
├── app/
│   ├── main.py                     # Khởi tạo FastAPI app, mount router, kết nối DB/Lifespan
│   ├── config.py                   # Đọc biến môi trường, thiết lập pydantic Settings
│   ├── database.py                 # Engine, SessionLocal, declarative_base
│   │
│   ├── models/                     # SQLAlchemy models theo nhóm dữ liệu liên quan
│   │   ├── user.py                 # users, roles, user_roles
│   │   ├── station.py              # Bảng trạm sạc
│   │   ├── charge_point.py         # charge_points, connectors
│   │   ├── id_tag.py / login_ip_attempt.py
│   │   ├── ocpp_message.py / connector_error.py / orphan_message.py
│   │   ├── charging_session.py / meter_value.py
│   │   ├── station_tariff.py        # station_tariffs, tariff_bands
│   │   └── charging_invoice.py / wallet_ledger.py / audit_log.py
│   │
│   ├── schemas/                    # Pydantic request/response validation
│   │   ├── user.py
│   │   ├── station.py
│   │   ├── charge_point.py
│   │   └── remote.py
│   │
│   ├── routers/                    # API Endpoints (Controllers)
│   │   ├── auth.py                 # Đăng nhập, đăng ký, xác thực
│   │   ├── stations.py             # CRUD Trạm sạc
│   │   ├── charge_points.py        # CRUD Trụ sạc
│   │   ├── monitoring.py / remote.py / ocpp.py
│   │   ├── sessions.py / audit.py / wallet.py
│   │   └── pages.py                # Render giao diện Jinja2 HTML cho Frontend
│   │
│   ├── core/                       # Utilities cốt lõi (dùng chung)
│   │   ├── security.py             # Băm mật khẩu, tạo token JWT
│   │   └── deps.py                 # Các dependency FastAPI (get_db, get_current_user)
│   │
│   ├── services/                   # Logic nghiệp vụ (Business logic thuần)
│   │   ├── ownership.py            # Lọc quyền sở hữu; không có models/ownership.py
│   │   ├── ocpp_parser.py / ocpp_handlers.py
│   │   ├── connection_manager.py / ocpp_status.py / jobs.py
│   │   └── pricing.py / session_energy.py / billing.py / wallet.py / audit.py
│   │
│   ├── ocpp/                       # Handler OCPP theo tin nhắn và ánh xạ trạng thái
│   │   ├── status_mapping.py / warning_throttler.py
│   │   └── handlers/               # boot_notification, heartbeat, status_notification, authorize, start_transaction, stop_transaction
│   │
│   └── dev_tools/
│       └── ocpp_simulator/         # PHẦN MỀM giả lập trụ sạc OCPP
│           ├── simulator.py        # Client độc lập; --count SIM và tuỳ chọn thêm 5 trụ mẫu, đủ đầu nối (T-55)
│           └── seed_codes.txt      # SIM-01..SIM-20, phải khớp seed_data.py
│
├── tests/                         # Unit test backend, không nằm trong mã ứng dụng
│   ├── conftest.py                # Fixture SQLite độc lập cho backend
│   └── unit/                      # Gồm test phiên T-36, Start/StopTransaction và tính kWh
│
├── alembic/versions/               # Lịch sử migration và merge revision đã có
├── alembic.ini                     # Cấu hình alembic
├── scripts/backup_postgres.sh      # Sao lưu/restore PostgreSQL trong Docker
├── csms.db                         # SQLite runtime local, không commit
├── requirements.txt                # Khai báo thư viện Python
├── requirements-dev.txt            # Ruff, Mypy, pytest, audit; không cài trong image runtime
├── pyproject.toml                  # Cấu hình lint/typecheck/coverage
├── seed_data.py                    # Script mồi dữ liệu ban đầu
├── pytest.ini                      # Cấu hình pytest
└── Dockerfile                      # Cấu hình build Docker cho backend
```

### Giới hạn cứng cho `backend/`

| Quy tắc | Giá trị | Vì sao |
| --- | --- | --- |
| Nơi được đọc biến môi trường | chỉ `app/config.py` | Quản lý cấu hình tập trung, dễ theo dõi bảo mật. |
| Phân tách Layer | `routers` gọi vào `services` hoặc tương tác qua DB, không phơi bày logic nghiệp vụ phức tạp trực tiếp tại Router. | Giữ Codebase gọn gàng, tái sử dụng, dễ test. |
| Simulator (`dev_tools/`) | không được import bất cứ logic trực tiếp nào từ `app/` | Simulator đóng vai trò thiết bị độc lập (Client) gọi lên Server để test khách quan. |

`services/ocpp_handlers.py` điều phối handler trong `ocpp/handlers/`; parser nằm
ở `services/ocpp_parser.py`. Đây là các phần phối hợp, không tạo bản sao handler
ở router hay một thư mục OCPP mới. Mã quyền sở hữu nằm ở `services/ownership.py`.
Giữ nguyên migration và revision đã chạy; không đổi tên/đánh lại số để làm đẹp cây.
Cây trên ghi cách nhóm model hiện có. Model mới vẫn theo quy ước một file cho
một bảng của đặc tả; việc tách các nhóm legacy phải thuộc task riêng có kiểm thử.

---

## 3. `frontend/` (frontend) — chi tiết

Không dùng framework SPA cồng kềnh. Sử dụng HTML render từ backend thông qua `pages.py` (Jinja2) kết hợp CSS và Vanilla JS.

```
frontend/
├── templates/                      # Chứa các file HTML (Jinja2)
│   ├── base.html                   # Layout gốc — MỌI trang khác extends từ đây
│   ├── auth/
│   │   └── login.html              # Màn hình đăng nhập
│   ├── stations/
│   │   ├── list.html               # Trang danh sách trạm sạc
│   │   └── form.html               # Trang thêm/sửa trạm sạc
│   ├── monitoring/
│   │   └── grid.html               # Lưới giám sát trạng thái realtime
│   ├── sessions/
│   │   ├── my_session.html         # Màn hình phiên sạc hiện tại của tài xế
│   │   ├── audit.html              # Tra cứu phiên/audit
│   │   └── anomaly_list.html       # Danh sách bất thường/cảnh báo
│   └── wallet/
│       ├── wallet.html             # Ví của tài xế
│       └── admin_drivers.html      # Quản lý tài xế
│
├── static/
│   ├── css/
│   │   ├── base.css / components.css # Style dùng chung
│   │   └── pages/                  # login, stations, monitoring, sessions, wallet, admin_drivers
│   └── js/
│       ├── api_client.js           # Module tập trung fetch API (Không rải rác fetch)
│       ├── auth_guard.js           # Context quyền từ server, safeNext dùng khi đăng nhập
│       ├── route_guard.js          # Helper /api/auth/me từ DANG-DAI; chưa được template nạp
│       ├── sse_client.js           # Kết nối Server-Sent Events (Realtime)
│       ├── form_guard.js           # Validate form cơ bản, chống double-submit
│       ├── layout.js               # Hành vi layout dùng chung
│       ├── restart_button.js       # Reset trụ qua backend, xác nhận và chặn lệnh trùng
│       └── pages/                  # Script thao tác DOM gắn với TỪNG TRANG cụ thể
│           ├── anomaly_list.js
│           ├── audit.js / admin_drivers.js / login.js
│           ├── monitoring_grid.js  # API/SSE, lọc từng trụ; chọn đầu nối/bắt đầu sạc đang là UI thử
│           ├── my_session.js
│           ├── stations_form.js
│           ├── stations_list.js
│           └── wallet.js
└── README.md                       # Hướng dẫn riêng cho frontend
```

### Giới hạn cứng cho `frontend/`

| Quy tắc | Giá trị |
| --- | --- |
| JS logic nghiệp vụ | CẤM viết trong `<script>` inline bên trong `.html`. Luôn tách file `.js` riêng và lưu vào `static/js/pages/`. |
| Gọi API | Luôn thông qua hàm của `static/js/api_client.js`, nghiêm cấm gọi `fetch(...)` tự do. |
| Component/Logic lặp lại | Tái sử dụng/viết gộp tại `base.html` hoặc đưa logic chung ra khỏi thư mục `pages/`. |

---

## 4. Đặt test, tài liệu và dữ liệu sinh ra ở đâu

| Loại thay đổi | Vị trí |
| --- | --- |
| Unit test backend | `backend/tests/unit/`, tái sử dụng fixture ở `backend/tests/conftest.py`. |
| Kiểm thử API, migration, mạng thật hoặc hợp đồng CI/CD | `tests/test_*.py`, fixture chung ở `tests/conftest.py`. |
| Nghiệm thu Docker/PostgreSQL thật | `tests/sprint2_docker_acceptance.py` dùng `docker-compose.acceptance.yml`; có cả ca số lượng trụ T-55. Tên file giữ để các lệnh CI hiện tại tiếp tục chạy. |
| Kiểm thử hành vi frontend | `tests/frontend_behavior.cjs`. |
| Kiểm thử phiên bản tài nguyên frontend và đăng xuất | `tests/test_frontend_assets.py`; template dùng `asset_url(...)` trong `backend/app/routers/pages.py`. |
| Báo cáo có thể đọc lại | `ketqua/T-xx_ket_qua.md`; báo cáo hai sprint trước ở `ketqua/sprint1_sprint2_audit.md`. |
| Quy tắc, vị trí code, đặc tả | Ba file `prompts/00_QUY_TAC_AGENT.md`, `01_CODEBASE_MAP.md`, `02_DAC_TA_DU_AN.md`. |
| Prompt QA backend | `prompts/backend_qa_prompt.md`; báo cáo ở `ketqua/backend_qa_prompt_ket_qua.md` và `ketqua/backend_test_results.md`. |
| Phân công và kế hoạch | `huongdan/Phan_cong_Sprint3.md` và workbook Excel trong `huongdan/`. |
| Hướng dẫn Git / ca test thủ công | `huongdan/git_clone_push.md` / `huongdan/test_cases_duc_sprint2.md`. |
| Kiểm thử sau đồng bộ main | `huongdan/kiem_thu_sau_pull_main.md`; báo cáo ở `ketqua/dong_bo_main.md`. |
| Tài liệu DANG-DAI | `huongdan/huong_dan_toan_dien_du_an_csms.md`; kế hoạch/báo cáo gốc ở `ketqua/ke_hoach_DANG_DAI_SCRUM_135.md`. |
| Lệnh kiểm chứng SCRUM-135 | `tests/verify_scrum135_live.py` gọi bộ pytest với DB tạm và kiểm thử JS; không đăng nhập server đang chạy. |

`.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, coverage,
database local và dump backup là dữ liệu sinh ra, đã được ignore. Không chuyển
chúng vào thư mục mã nguồn hoặc đưa bản sao plugin/skill vào repo. Các file
`SPRINT_1.md`, `02_CODING_STANDARDS.md`, `03_SSD_SPEC.md`, `sprint1.xlsx` không nằm
trong cây hiện tại; tra cứu ba prompt ở trên thay vì tạo lại chúng.

## 5. Quy tắc "không tạo file rác" khi vibe code

1. **Trước khi tạo file mới**: Tra cứu cấu trúc ở mục 2/3 xem đã có thư mục thích hợp chưa. Nếu AI dự định sinh code ngoài cấu trúc này → Yêu cầu dừng và hỏi lại thay vì tự phịa thư mục.
2. **Không tạo phiên bản song song**: Nghiêm cấm tạo `xxx_new.py`, `xxx_v2.html`, `test_old.py`. Chỉ sửa trực tiếp file và dựa vào Git để theo dõi lịch sử.
3. **Mọi thay đổi CSDL**: Bắt buộc tạo qua file Migration của Alembic (trong `alembic/`), không thay đổi model trực tiếp mà không có file migration.
4. **Không tạo script dùng 1 lần rồi quên**: Các đoạn test debug ngắn không được đẩy (commit) lên nhánh chính.
5. **Code giả lập vs Code nghiệp vụ**: Hệ thống này phục vụ quản lý web. Toàn bộ logic giao tiếp thiết bị thực tế đã được chuyển thành code phần mềm giả lập tại `dev_tools/ocpp_simulator/`. Tuyệt đối không thêm/tưởng tượng ra các file phần cứng C/C++.
