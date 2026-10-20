# CSMS — Hệ thống quản lý trạm sạc xe điện

CSMS (Charging Station Management System) quản lý trạm sạc, trụ sạc và phiên sạc theo giao thức **OCPP 1.6J**. Backend dùng **FastAPI**, giao diện dùng **Jinja2, HTML, CSS và JavaScript**, dữ liệu lưu trong **PostgreSQL** khi chạy Docker hoặc **SQLite** khi chạy local trên Windows.

Trụ sạc trong môi trường phát triển là client giả lập; dự án không điều khiển phần cứng sạc thật.

## Chức năng chính

- Quản lý trạm, trụ sạc, đầu nối và biểu giá theo khung giờ.
- Nhận thông điệp OCPP 1.6J qua WebSocket, theo dõi trạng thái trụ trực tiếp qua API/SSE và gửi lệnh từ xa.
- Quản lý phiên sạc, số đo điện năng, hóa đơn, phiên bất thường và đối chiếu kWh/tài chính.
- Hỗ trợ đặt chỗ, ví tài xế, gói thuê bao, báo cáo doanh thu, cảnh báo vận hành và nhật ký kiểm toán.
- Phân quyền cho quản trị viên, chủ trạm, vận hành viên, kế toán và tài xế.
- Giao diện responsive được phục vụ từ FastAPI; không cần cài framework frontend riêng.

## Yêu cầu

| Công cụ | Phiên bản |
|---|---|
| Python | 3.11 trở lên |
| Docker Engine/Desktop | 24 trở lên, nếu chạy bằng Docker |
| Docker Compose | v2.20 trở lên, nếu chạy bằng Docker |
| Node.js | 22, chỉ cần khi chạy kiểm tra JavaScript |

## Chạy bằng Docker Compose

Tại thư mục gốc của repo, tạo file cấu hình lần đầu:

```powershell
Copy-Item .env.example .env
```

Đổi `CSMS_DB_PASSWORD` và `SECRET_KEY` trong `.env` trước khi triển khai dùng chung. Sau đó chạy:

```powershell
docker compose up --build -d
```

Mở [http://localhost:8000/login](http://localhost:8000/login). Xem log bằng `docker compose logs -f app`; dừng bằng `docker compose down`. Lệnh `down` giữ dữ liệu PostgreSQL trong volume `postgres_data`. Chỉ dùng `docker compose down -v` khi chủ động muốn xóa các volume và dữ liệu của chúng.

Compose khởi động PostgreSQL 15, chờ database sẵn sàng rồi chạy migration Alembic trước khi phục vụ ứng dụng. `docker-compose.override.yml` được Compose tự nạp khi chạy local để mount `frontend/` vào container, giúp cập nhật giao diện mà không cần build lại image.

## Chạy trực tiếp trên Windows

PowerShell tại thư mục gốc:

```powershell
.\run.ps1
```

Script tạo hoặc sửa lại `.venv` nếu môi trường không hợp lệ, cài thư viện từ `backend/requirements.txt`, tạo `.env` từ `.env.example` nếu còn thiếu, chạy migration và khởi động server. Mặc định ứng dụng dùng SQLite tại `backend/csms.db` và bật 20 client giả lập `SIM-*` cùng 5 trụ demo.

Một số tuỳ chọn:

```powershell
.\run.ps1 -SimulatorCount 3 -SkipDemoStations # Chạy 3 trụ SIM-*, không thêm trụ demo
.\run.ps1 -SkipSimulator                    # Tắt simulator
```

Truy cập [http://localhost:8000/login](http://localhost:8000/login). Dừng server bằng `Ctrl+C`.

## Trụ OCPP giả lập

Khi `APP_ENV=development`, ứng dụng seed các mã `SIM-01` đến `SIM-20`. Với Docker Compose, bật profile simulator:

```powershell
docker compose --profile ocpp-simulator up -d --build simulator
docker compose logs -f simulator
```

Mặc định simulator kết nối 20 trụ `SIM-*` tới `ws://app:8000/ocpp`. Có thể đặt `CSMS_SIMULATOR_COUNT` từ 1 đến 20 hoặc thay `CSMS_SIMULATOR_URL` trong `.env`. Để kết nối thêm 5 trụ demo ở Vincom, AEON và Thủ Thiêm, đặt `CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS=true` rồi khởi động lại simulator. Mở trang `/monitoring` để xem trạng thái.

## Tài khoản demo

Các tài khoản này chỉ dùng trong môi trường phát triển/demo. Không dùng chúng trên production. Seed demo chạy khi `APP_ENV=development`.

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Quản trị viên | `admin@csms.local` | `Admin@2024!` |
| Chủ trạm | `owner@csms.local` | `Owner@2024!` |
| Vận hành viên | `operator@csms.local` | `Operator@2024!` |
| Kế toán | `accountant@csms.local` | `Accountant@2024!` |
| Tài xế | `driver@csms.local` | `Driver@2024!` |
| Tài xế demo 2 | `driver2@csms.local` | `Driver2@2024!` |

Thẻ RFID giả lập mặc định của tài xế đầu tiên là `DEMO-DRIVER-0005`. ID và thẻ có thể khác nếu database đã có dữ liệu trước đó.

## Kiểm tra mã nguồn

CI trên GitHub Actions chạy Ruff, Mypy, kiểm tra lỗ hổng dependency, pytest, kiểm tra JavaScript, build Docker và các bước nghiệm thu OCPP bằng Docker. Để chạy các bước Python chính từ PowerShell tại thư mục gốc:

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Push-Location backend
..\.venv\Scripts\python.exe -m ruff check app tests alembic ../tests ../scripts
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest tests ../tests --ignore=../tests/test_scrum182_20charger_scenario.py --tb=short -v
Pop-Location
node --test tests/frontend_behavior.cjs
```

Các kiểm tra nghiệm thu cần Docker. Bộ gate 20 trụ có thể chạy từ thư mục gốc sau khi cài dependency Python:

```powershell
python scripts/run_sprint3_ci.py
```

Runner tạo stack PostgreSQL/app riêng, chạy ba lượt mô phỏng 20 trụ và ghi báo cáo vào `outputs/sprint3-ci/`.

## Database và migration

- Docker Compose dùng PostgreSQL 15 và volume `postgres_data`.
- `run.ps1` dùng SQLite tại `backend/csms.db`.
- Ứng dụng tự chạy `alembic upgrade head` khi khởi động. Không xóa hoặc đổi revision migration đã được áp dụng.
- File mẫu cấu hình và các tuỳ chọn khác nằm trong [.env.example](.env.example); cấu hình local `.env` không được commit.

Chạy lệnh Alembic từ `backend/`:

```powershell
alembic current
alembic upgrade head
```

## Cấu trúc repo

```text
.
├── .github/workflows/       # CI và deploy staging
├── backend/
│   ├── app/                 # FastAPI, API, OCPP, nghiệp vụ và dữ liệu
│   ├── alembic/             # Migration database
│   ├── tests/               # Unit test backend
│   └── Dockerfile
├── frontend/
│   ├── templates/           # Template Jinja2
│   └── static/              # CSS, JavaScript và dữ liệu mẫu
├── tests/                   # Test tích hợp, frontend và acceptance
├── scripts/                 # Công cụ CI/acceptance
├── huongdan/                # Workbook tham khảo dự án
├── ketqua/                  # Dữ liệu kiểm thử dạng JSON
├── docker-compose.yml
├── docker-compose.acceptance.yml
├── run.ps1                  # Chạy local trên Windows
└── run.py                   # Khởi động Uvicorn
```

## CI và deploy

`.github/workflows/ci.yml` chạy khi push, pull request hoặc được gọi thủ công. `.github/workflows/deploy.yml` gọi CI và chỉ deploy staging khi push vào `main` hoặc `master`; push vào `Develop` chạy CI nhưng không tự deploy staging.
