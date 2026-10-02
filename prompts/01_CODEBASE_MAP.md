# Codebase Map — Nền tảng vận hành trạm sạc xe điện (CSMS)

> Đây là **dự án web thuần**: FastAPI (Python) phía server + HTML/CSS/JS phía
> trình duyệt. Không có mạch điện tử, không có lập trình nhúng, không có
> firmware thật. "Trụ sạc" trong toàn bộ dự án là **phần mềm giả lập** (một
> script Python giả lập tin nhắn OCPP), không phải thiết bị vật lý.
>
> Tài liệu này là **nguồn sự thật duy nhất** về "file này đặt ở đâu". Khi vide
> code (AI sinh code), luôn đọc file này trước để biết đặt code mới vào thư mục
> nào — không tự sáng tạo thư mục mới, không tạo file `_v2`, `_final`, `_copy`.

## 0. Ánh xạ với repo hiện tại

| Thư mục trong repo | Vai trò thực sự | Ghi chú |
| --- | --- | --- |
| `frontend/` | **Frontend** — HTML/CSS/JS thuần | Giao diện phía client hiển thị dựa trên Jinja2 template. Trước đây bị nhầm là `giaodien/`. |
| `backend/` | **Backend** — toàn bộ Python/FastAPI (REST API + WebSocket OCPP + job nền) | Logic server, giao tiếp CSDL, và giả lập thiết bị. Trước đây bị nhầm là `hardware/`. |
| `tests/` (root) | **Testing / QA** | Chứa các tài liệu kiểm thử QA, test dùng chung toàn hệ thống. |
| `prompts/` | **Hướng dẫn AI (Prompts)** | Chứa các quy ước chuẩn để đảm bảo AI sinh code đúng chuẩn. |

---

## 1. Cây thư mục tổng (mức gốc)

```
TTCS_K8S4_N5/
├── backend/                  # BACKEND — FastAPI, toàn bộ logic server (Python)
├── frontend/                 # FRONTEND — HTML/CSS/JS thuần
├── prompts/                  # Chứa các file định hướng, quy ước cho AI
├── tests/                    # Tài liệu QA, script test tổng thể
├── ketqua/                   # Lưu kết quả test, báo cáo
├── huongdan/                 # Chứa các tài liệu hướng dẫn
├── docker-compose.yml        # Cấu hình deploy Docker (app + db + redis...)
├── .env / .env.example       # File cấu hình biến môi trường
├── run.py                    # Script khởi chạy ứng dụng 
├── README.md                 # Tài liệu mô tả dự án
└── sprint1.xlsx              # File theo dõi công việc Sprint
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
│   ├── models/                     # SQLAlchemy models — 1 file = 1 bảng
│   │   ├── user.py                 # Bảng người dùng
│   │   ├── station.py              # Bảng trạm sạc
│   │   ├── charge_point.py         # Bảng trụ sạc
│   │   └── ownership.py            # Bảng quản lý quyền sở hữu
│   │
│   ├── schemas/                    # Pydantic request/response validation
│   │   ├── user.py
│   │   ├── station.py
│   │   └── charge_point.py
│   │
│   ├── routers/                    # API Endpoints (Controllers)
│   │   ├── auth.py                 # Đăng nhập, đăng ký, xác thực
│   │   ├── stations.py             # CRUD Trạm sạc
│   │   ├── charge_points.py        # CRUD Trụ sạc
│   │   └── pages.py                # Phục vụ render giao diện Jinja2 HTML cho Frontend
│   │
│   ├── core/                       # Utilities cốt lõi (dùng chung)
│   │   ├── security.py             # Băm mật khẩu, tạo token JWT
│   │   └── deps.py                 # Các dependency FastAPI (get_db, get_current_user)
│   │
│   ├── services/                   # Logic nghiệp vụ (Business logic thuần)
│   │
│   ├── dev_tools/
│   │   └── ocpp_simulator/         # PHẦN MỀM giả lập trụ sạc OCPP
│   │
│   └── tests/                      # Unit test/ Integration test riêng cho Backend
│       ├── conftest.py             # Fixtures dùng chung cho pytest
│       └── unit/                   # Các script test theo mức độ unit
│
├── alembic/                        # Công cụ migration Database (thay đổi schema)
├── alembic.ini                     # Cấu hình alembic
├── csms.db                         # Database SQLite
├── requirements.txt                # Khai báo thư viện Python
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
│   │   └── anomaly_list.html       # Danh sách bất thường/cảnh báo
│   └── wallet/                     # Các view quản lý ví
│
├── static/
│   ├── css/                        # Style dùng chung hoặc riêng cho view
│   └── js/
│       ├── api_client.js           # Module tập trung fetch API (Không rải rác fetch)
│       ├── sse_client.js           # Kết nối Server-Sent Events (Realtime)
│       ├── form_guard.js           # Validate form cơ bản, chống double-submit
│       └── pages/                  # Script thao tác DOM gắn với TỪNG TRANG cụ thể
│           ├── anomaly_list.js
│           ├── monitoring_grid.js
│           ├── my_session.js
│           ├── stations_form.js
│           ├── stations_list.js
│           └── wallet.js
```

### Giới hạn cứng cho `frontend/`

| Quy tắc | Giá trị |
| --- | --- |
| JS logic nghiệp vụ | CẤM viết trong `<script>` inline bên trong `.html`. Luôn tách file `.js` riêng và lưu vào `static/js/pages/`. |
| Gọi API | Luôn thông qua hàm của `static/js/api_client.js`, nghiêm cấm gọi `fetch(...)` tự do. |
| Component/Logic lặp lại | Tái sử dụng/viết gộp tại `base.html` hoặc đưa logic chung ra khỏi thư mục `pages/`. |

---

## 4. Quy tắc "không tạo file rác" khi vide code

1. **Trước khi tạo file mới**: Tra cứu cấu trúc ở mục 2/3 xem đã có thư mục thích hợp chưa. Nếu AI dự định sinh code ngoài cấu trúc này → Yêu cầu dừng và hỏi lại thay vì tự phịa thư mục.
2. **Không tạo phiên bản song song**: Nghiêm cấm tạo `xxx_new.py`, `xxx_v2.html`, `test_old.py`. Chỉ sửa trực tiếp file và dựa vào Git để theo dõi lịch sử.
3. **Mọi thay đổi CSDL**: Bắt buộc tạo qua file Migration của Alembic (trong `alembic/`), không thay đổi model trực tiếp mà không có file migration.
4. **Không tạo script dùng 1 lần rồi quên**: Các đoạn test debug ngắn không được đẩy (commit) lên nhánh chính.
5. **Code giả lập vs Code nghiệp vụ**: Hệ thống này phục vụ quản lý web. Toàn bộ logic giao tiếp thiết bị thực tế đã được chuyển thành code phần mềm giả lập tại `dev_tools/ocpp_simulator/`. Tuyệt đối không thêm/tưởng tượng ra các file phần cứng C/C++.
