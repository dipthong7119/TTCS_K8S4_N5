# frontend/ — Frontend CSMS

> HTML/CSS/JS thuần, render bởi Jinja2 (FastAPI serves templates).
> Không dùng React/Vue. Tất cả JS logic nghiệp vụ nằm trong file `.js` riêng.
> Cây hiện tại được cập nhật ở `../prompts/01_CODEBASE_MAP.md`.

## Cây thư mục

```
frontend/
├── templates/
│   ├── base.html                   # Layout gốc — MỌI trang extends từ đây
│   ├── auth/
│   │   └── login.html              # T-05 — form đăng nhập (mẫu cho mọi form)
│   ├── stations/
│   │   ├── list.html               # T-09 — danh sách trạm
│   │   └── form.html               # Thêm/sửa trạm + quản lý trụ
│   ├── monitoring/
│   │   └── grid.html               # T-24 — lưới trạm/trụ/đầu nối realtime
│   ├── sessions/
│   │   ├── my_session.html         # T-48 — lịch sử sạc tài xế
│   │   ├── audit.html              # Tra cứu phiên/audit
│   │   └── anomaly_list.html       # T-54 — phiên bất thường
│   └── wallet/
│       ├── admin_drivers.html      # Quản lý tài xế
│       └── wallet.html             # S-40 — ví điện tử
│
└── static/
    ├── css/
    │   ├── base.css                # Biến màu (CSS custom props), spacing, typography, app shell
    │   ├── components.css          # Btn, form, card, badge, table, modal, toast... (tái sử dụng)
    │   └── pages/
    │       ├── login.css           # CSS đặc thù trang login
    │       ├── stations.css        # CSS đặc thù trang trạm
    │       ├── monitoring.css      # CSS đặc thù lưới giám sát
    │       ├── sessions.css        # CSS đặc thù trang phiên sạc
    │       ├── admin_drivers.css   # CSS trang quản lý tài xế
    │       └── wallet.css          # CSS đặc thù trang ví
    └── js/
        ├── api_client.js           # MỌI lời gọi API đi qua đây (không rải fetch)
        ├── auth_guard.js           # Context quyền và chuyển hướng đăng nhập an toàn
        ├── route_guard.js          # Helper /auth/me chưa được template nạp
        ├── sse_client.js           # Kết nối SSE dùng chung (T-25)
        ├── form_guard.js           # Chặn bấm lưu 2 lần (T-09, T-11)
        ├── layout.js               # Hành vi layout chung
        ├── restart_button.js       # Component Reset trụ
        └── pages/
            ├── login.js / audit.js / admin_drivers.js
            ├── stations_list.js    # Logic trang danh sách trạm
            ├── stations_form.js    # Logic trang thêm/sửa trạm
            ├── monitoring_grid.js  # Logic lưới giám sát + SSE handler
            ├── my_session.js       # Logic trang lịch sử sạc tài xế
            ├── anomaly_list.js     # Logic trang phiên bất thường
            └── wallet.js           # Logic trang ví điện tử
```

## Quy ước class CSS (BEM đơn giản)

Giám sát dùng dữ liệu API/SSE từ simulator OCPP, không có bộ mẫu chạy riêng
trên trình duyệt. Bộ lọc và tìm mã trụ giữ đúng các trụ khớp trong từng trạm,
kể cả khi mở chi tiết hoặc nhận SSE. `Unavailable` hiển thị tạm ngừng;
`Faulted` hoặc mã lỗi đầu nối được tính là lỗi, mỗi trụ chỉ đếm một lần.
Các template dùng `asset_url(...)` từ router trang để gắn phiên bản theo file
vào URL JS/CSS. Giữ helper này khi thêm trang để tránh nạp script cũ từ cache.

Sau gộp DANG-DAI, chi tiết trạm có danh sách chọn đầu nối và nút bắt đầu sạc
(SCRUM-190). Chỉ đầu nối Available của trụ online chọn được. Nút hiện thông báo
bản thử giao diện; chưa gọi API bắt đầu phiên. Trạng thái chờ 60 giây và các lỗi
từ chối/bận/hết thời gian chưa được nối vào luồng chạy (SCRUM-191/192).

Đăng nhập và hiện/ẩn mật khẩu đã có trước lần gộp này. Trang login sử dụng API
đăng nhập và tài khoản trong database; chế độ mock login ngoài yêu cầu đã gỡ.

| Pattern | Ví dụ |
|---|---|
| Block | `.card`, `.btn`, `.badge`, `.sidebar` |
| Element | `.card__title`, `.sidebar__link`, `.badge--charging` |
| Modifier | `.btn--primary`, `.badge--online`, `.sidebar__link.is-active` |

## Quy tắc cứng (xem prompts/01_CODEBASE_MAP.md và 00_QUY_TAC_AGENT.md ở gốc repo)

| Quy tắc | Giá trị |
|---|---|
| Trạng thái | Luôn nhãn chữ + màu (không chỉ màu — T-24 NFR) |
| Bề rộng tối thiểu | 360px |
| CSS trùng lặp | Cấm — ≥2 trang → chuyển vào `components.css` |
| JS inline logic | Cấm trong `<script>` HTML — luôn tách file `.js` |
| Gọi API | Luôn qua `api_client.js` |
| File JS trang | ≤ ~100 dòng |
| File CSS trang | ≤ ~80 dòng |
| Template `.html` | ≤ ~150 dòng |

## Cách thêm trang mới

1. Tạo template trong đúng thư mục con (xem cây trên)
2. Template **phải** `{% extends "base.html" %}` và set `{% set active_page = "..." %}`
3. Nếu cần CSS riêng: tạo file trong `static/css/pages/`, import qua `{% block extra_css %}`
4. Nếu cần JS riêng: tạo file trong `static/js/pages/`, import qua `{% block extra_js %}`
5. Mọi gọi API: thêm vào `api_client.js`, không viết `fetch(...)` trực tiếp trong trang JS
