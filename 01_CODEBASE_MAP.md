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

| Thư mục trong repo (ảnh bạn gửi) | Vai trò thực sự | Ghi chú |
| --- | --- | --- |
| `giaodien/` | **Frontend** — HTML/CSS/JS thuần | Không dùng framework JS nặng, xem lý do ở mục 2 |
| **`hardware/`** | **Backend** — toàn bộ Python/FastAPI (REST API + WebSocket OCPP + job nền) | Tên thư mục giữ nguyên như đã tạo trong repo; đừng để tên đánh lừa — bên trong 100% là code phần mềm, không có gì "phần cứng" |
| `main.py` (ở root) | Nên di chuyển vào `hardware/app/main.py` | Root không nên có code chạy trực tiếp |

> Nếu sau này bạn thấy tên `hardware/` gây nhầm lẫn cho người mới vào repo, có
> thể đổi tên thư mục thành `backend/` bất cứ lúc nào (chỉ là `git mv`, không
> ảnh hưởng logic) — nhưng vì bạn muốn giữ tên đã tạo, toàn bộ tài liệu dưới
> đây dùng đúng tên `hardware/`.

---

## 1. Cây thư mục tổng (mức gốc)

```
TTCS_K8S4_N5/
├── hardware/                 # BACKEND — FastAPI, toàn bộ logic server (Python)
├── giaodien/                 # FRONTEND — HTML/CSS/JS thuần
├── docker-compose.yml        # app + db + N trụ ảo (T-01, T-55)
├── .env.example               # KHÔNG commit .env thật (bí mật qua biến môi trường)
├── README.md
└── HD.txt / hướng_dẫn_clone_push.txt   # giữ nguyên, không đụng
```

Quy tắc cứng: **mọi thứ Python nằm trong `hardware/`, mọi thứ tĩnh
(HTML/CSS/JS) nằm trong `giaodien/`.** Không có file `.py` rải ở root ngoài
script CLI tiện ích, không có `<script>` logic nghiệp vụ nhúng thẳng trong HTML.

---

## 2. `hardware/` (= BACKEND) — chi tiết

Kiến trúc phân lớp, **một handler OCPP = một file** (đúng quy ước T-16: *"cấu
trúc file của nó là mẫu cho mọi handler sau"*).

```
hardware/
├── app/
│   ├── main.py                     # khởi tạo FastAPI app, mount router, lifespan
│   ├── config.py                   # đọc biến môi trường (pydantic Settings) — nơi DUY NHẤT đọc os.environ
│   ├── database.py                 # engine, session, Base
│   │
│   ├── models/                     # SQLAlchemy models — 1 file = 1 bảng hoặc 1 nhóm bảng liên quan chặt
│   │   ├── user.py                 # users, roles, user_roles
│   │   ├── station.py              # stations
│   │   ├── charge_point.py         # charge_points, connectors
│   │   ├── session.py              # charging_sessions, meter_values, orphan_messages
│   │   ├── ocpp_message.py         # ocpp_messages (chống trùng — S-14)
│   │   ├── tariff.py               # biểu giá (E-05, từ sprint 4)
│   │   ├── wallet.py               # wallets, ledger_entries (E-06, từ sprint 5)
│   │   └── audit_log.py            # audit_logs (chỉ ghi thêm — T-57)
│   │
│   ├── schemas/                    # Pydantic request/response — 1 file khớp tên với models/
│   │   ├── user.py
│   │   ├── station.py
│   │   ├── charge_point.py
│   │   ├── session.py
│   │   └── ...
│   │
│   ├── routers/                    # REST endpoints — nhóm theo epic, KHÔNG nhóm theo CRUD
│   │   ├── auth.py                 # S-02: đăng nhập, khoá tạm
│   │   ├── stations.py             # S-04: CRUD trạm (đi qua ownership filter)
│   │   ├── charge_points.py        # S-05: thêm trụ/đầu nối
│   │   ├── monitoring.py           # S-11: cây trạng thái + SSE endpoint (T-23, T-25)
│   │   ├── sessions.py             # S-22, S-23, S-24: phiên của tài xế + remote start/stop
│   │   ├── wallet.py                # S-35..S-41: ví, webhook nạp tiền
│   │   └── audit.py                 # S-27: tra nhật ký
│   │
│   ├── ocpp/                       # LÕI KỸ THUẬT — nơi xử lý giao thức OCPP 1.6J qua WebSocket. Vẫn là phần mềm thuần, KHÔNG liên quan phần cứng thật.
│   │   ├── ws_gateway.py           # endpoint WebSocket /ocpp/{code} — chỉ lo bắt tay + định tuyến (T-12, T-13, T-28)
│   │   ├── frame_codec.py          # module THUẦN: đọc/ghi CALL/CALLRESULT/CALLERROR (T-14) — không phụ thuộc WebSocket, test không cần mở kết nối
│   │   ├── dispatcher.py           # tra ocpp_messages chống trùng (T-30) rồi gọi đúng handler
│   │   ├── outbound.py             # gửi CALL từ server -> trụ ảo, chờ CALLRESULT theo mã (T-34)
│   │   └── handlers/               # MỖI FILE = ĐÚNG MỘT ACTION OCPP — không gộp nhiều action vào 1 file
│   │       ├── boot_notification.py     # S-08
│   │       ├── heartbeat.py             # S-09
│   │       ├── status_notification.py   # S-10
│   │       ├── authorize.py             # S-15
│   │       ├── start_transaction.py     # S-17
│   │       ├── stop_transaction.py      # S-18
│   │       ├── meter_values.py          # S-19, S-20
│   │       ├── reset.py                 # S-16
│   │       └── remote_stop_transaction.py  # S-23
│   │
│   ├── services/                   # Logic nghiệp vụ THUẦN (pure function ưu tiên) — routers và handlers gọi vào đây, không xử lý trực tiếp trong router
│   │   ├── ownership.py            # hàm lọc sở hữu DÙNG CHUNG (T-07) — CHỈ một chỗ, không copy vào từng query
│   │   ├── energy_calc.py          # tính kWh từ số đo (T-39) — hàm thuần, test theo bảng
│   │   ├── billing/                # E-05, sprint 4 trở đi
│   │   │   ├── segment_split.py    # chia đoạn theo khung giờ — HÀM THUẦN, không đọc DB (S-30, NFR)
│   │   │   └── invoice.py
│   │   └── wallet_service.py       # trừ ví trong cùng transaction với lập hoá đơn (S-37)
│   │
│   ├── jobs/                       # job nền — theo mẫu T-26, ĐĂNG KÝ Ở MỘT NƠI DUY NHẤT
│   │   ├── scheduler.py            # nơi duy nhất khai báo job + chu kỳ chạy
│   │   ├── offline_detector.py     # T-26: quét last_seen_at
│   │   ├── stale_message_cleanup.py # T-31: dọn ocpp_messages > 7 ngày
│   │   └── stale_session_detector.py # T-53: phiên treo -> bất thường
│   │
│   ├── core/
│   │   ├── security.py             # argon2id hash, cookie httpOnly
│   │   ├── deps.py                 # FastAPI Depends: current_user, require_role(...)
│   │   └── logging.py              # cấu hình log — CHẶN log mật khẩu/token/mã thẻ đầy đủ/PII
│   │
│   ├── dev_tools/
│   │   └── ocpp_simulator/         # PHẦN MỀM giả lập trụ sạc, chỉ dùng cho dev/CI — KHÔNG phải mạch/thiết bị thật
│   │       ├── simulator.py        # simulator chọn ở K-01 (mã nguồn mở hoặc tự viết, lý do chọn ghi trong docs/spike/)
│   │       ├── scenarios/          # kịch bản test: ngắt-nối ngẫu nhiên (T-46), gửi trùng tin nhắn (T-31)
│   │       └── seed_codes.txt      # mã trụ ảo có TIỀN TỐ RIÊNG, tách khỏi dữ liệu thật (T-55 NFR)
│   │
│   └── tests/
│       ├── unit/                   # test hàm thuần (frame_codec, energy_calc, segment_split...)
│       ├── integration/            # test qua DB thật (theo mẫu T-27, T-29)
│       ├── ocpp_scenarios/         # test tích hợp dùng dev_tools/ocpp_simulator (T-46) — chạy trong CI
│       └── billing_truth_table/    # ĐÁP ÁN TÍNH TAY — S-32, lưu riêng, có tên người tính + ngày, KHÔNG sinh bằng mã
│
├── alembic/                        # migrations — đặt tên theo mẫu T-01: snake_case, khoá chính id, created_at/updated_at
│   └── versions/
├── requirements.txt
├── Dockerfile
└── pytest.ini
```

### Giới hạn cứng cho `hardware/` (backend — chặn "file rác" khi vide code)

| Quy tắc | Giá trị | Vì sao |
| --- | --- | --- |
| Độ dài tối đa 1 file | **~250 dòng** (handler OCPP: ~150 dòng) | Một handler chỉ xử lý một action — T-16 |
| Số hàm/class public tối đa mỗi file | 1 handler, hoặc 1 service class | Đúng mẫu "cấu trúc file là mẫu cho handler sau" |
| Nơi được đọc `os.environ` | chỉ `config.py` | NFR lặp lại nhiều lần: "bí mật nạp từ biến môi trường" |
| Nơi được viết điều kiện lọc sở hữu | chỉ `services/ownership.py` | T-07: "một hàm duy nhất, không chép tay vào từng truy vấn" |
| Nơi được ghi audit log | chỉ qua `core/logging.py` hoặc hàm `ghi_nhat_ky` dùng chung | T-57 |
| File cấm tạo | `utils.py`, `helpers.py`, `common.py` chung chung | "Rác" thường bắt đầu từ các file này — mọi hàm phải có nhà rõ ràng theo bảng trên |
| Simulator (`dev_tools/ocpp_simulator/`) | không được import bất cứ gì từ `app/` và ngược lại | Simulator giả lập **phía client**, phải độc lập với code server để test khách quan |

---

## 3. `giaodien/` (frontend) — chi tiết

Không dùng React/Vue (backlog không yêu cầu SPA phức tạp, chỉ cần hoạt động ở
360px — T-24, T-48). Dùng HTML render từ backend (Jinja2, do FastAPI phục vụ) +
CSS thuần + JS thuần cho phần realtime (SSE — T-25).

```
giaodien/
├── templates/                      # Jinja2 — khớp với routers/ tương ứng trong hardware/app/routers/
│   ├── base.html                   # layout gốc — MỌI trang khác extends từ đây, không copy <head>
│   ├── auth/
│   │   └── login.html              # T-05 — bố cục form MẪU cho mọi form sau
│   ├── stations/
│   │   ├── list.html               # T-09
│   │   └── form.html               # dùng lại bố cục form của login.html
│   ├── monitoring/
│   │   └── grid.html               # T-24 — lưới trạm/trụ/đầu nối
│   ├── sessions/
│   │   ├── my_session.html         # T-48 — màn hình tài xế, MẪU cho các màn hình E-11 sau
│   │   └── anomaly_list.html       # T-54
│   └── wallet/
│       └── wallet.html             # S-40
│
├── static/
│   ├── css/
│   │   ├── base.css                 # biến màu, spacing, typography DÙNG CHUNG — mọi trang import file này trước
│   │   ├── components.css           # form, nút, bảng, thẻ trạng thái — TÁI SỬ DỤNG, không viết CSS riêng lặp lại mỗi trang
│   │   └── pages/                   # CSS đặc thù từng trang (ít, chỉ khi thật sự cần)
│   └── js/
│       ├── api_client.js            # MỌI lời gọi API đi qua đây — không rải fetch(...) khắp nơi
│       ├── sse_client.js            # kết nối SSE dùng chung (T-25) — mọi trang cần realtime import file này
│       ├── form_guard.js            # chặn bấm lưu 2 lần (yêu cầu lặp lại ở nhiều task: T-09, T-11...)
│       └── pages/                   # JS đặc thù từng trang, đặt tên trùng tên template
└── README.md                        # quy ước class CSS, cách thêm trang mới
```

### Giới hạn cứng cho `giaodien/`

| Quy tắc | Giá trị |
| --- | --- |
| Trạng thái phân biệt | luôn nhãn chữ + màu, không chỉ màu (T-24 NFR — người mù màu) |
| Bề rộng tối thiểu phải chạy đúng | 360px (NFR của E-11 lặp lại nhiều lần) |
| CSS trùng lặp | cấm — nếu style xuất hiện ở ≥2 trang, chuyển vào `components.css` |
| JS logic nghiệp vụ | cấm viết trong `<script>` inline trong `.html` — luôn tách file `.js` riêng |
| Gọi API | luôn qua `static/js/api_client.js`, không rải `fetch(...)` khắp nơi |

---

## 4. Quy tắc "không tạo file rác" khi vide code

1. **Trước khi tạo file mới**: tra bảng ở mục 2/3 xem đã có "nhà" cho nó chưa.
   Nếu AI sinh code có ý định tạo file ngoài cây trên → dừng lại, hỏi lại thay
   vì tự bịa thư mục.
2. **Không tạo phiên bản song song**: cấm `xxx_new.py`, `xxx_v2.html`,
   `test_old.py`. Sửa trực tiếp file cũ, dùng git để giữ lịch sử.
3. **Không tạo script một lần rồi bỏ quên**: nếu là script debug tạm, đặt trong
   `hardware/scripts/` (tạo khi cần) và xoá sau khi dùng xong trước khi merge.
4. **1 migration = 1 thay đổi schema rõ ràng**, đặt tên theo mẫu T-01
   (`snake_case`, mô tả ngắn, có thể lùi được).
5. **Mọi file mới phải xuất hiện trong PR đi kèm lý do** — khớp với DoD: *"Code
   review đã duyệt bởi ít nhất một thành viên khác"*.
6. **Không thêm code phần cứng/nhúng dưới bất kỳ hình thức nào** — đây là dự án
   web 100%; mọi thứ mô phỏng "trụ sạc" chỉ là script Python trong
   `hardware/app/dev_tools/ocpp_simulator/`.
