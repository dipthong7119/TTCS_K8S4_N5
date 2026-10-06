# Đồng bộ main và sắp xếp code mới

Ngày **06/10/2026**. Phạm vi: pull main, giữ thay đổi local T-55 và dọn cấu trúc;
không triển khai thêm T-56 hoặc SCRUM-185.

## Git và bảo toàn thay đổi

- `main`: `ea94972` → `bff03696d42b57bdfd6a9c85e3ecc93c26948642`, fast-forward 13 commit.
- Trước pull, dùng Git stash có cả file untracked để giữ thay đổi local, gồm workbook.
  Stash an toàn vẫn giữ trong Git: `b2ea2bdbf70be35721d81d55120c1ff6441547d5`.
  Không tạo thư mục backup trong dự án.
- Áp dụng lại toàn bộ T-55 và thay đổi sắp xếp trước đó. Xung đột modify/delete
  duy nhất là nhật ký mới từ upstream; giữ nội dung tại `ketqua/nhat_ky.md`.
- Giữ các file người dùng đã xoá, `.env` thực tế, dữ liệu PostgreSQL và SQLite.
- Không commit/push; các thay đổi local giữ trạng thái unstaged như trước pull.

## Sắp xếp và sửa lỗi đồng bộ

- Chuyển 4 file test mới từ `backend/app/tests/unit/` sang `backend/tests/unit/`:
  `test_charging_sessions_36.py`, `test_session_energy.py`,
  `test_start_transaction.py`, `test_stop_transaction.py`.
- Sửa đường dẫn backend của test migration T-36 từ `parents[3]` thành `parents[2]`.
  Không thay đổi migration hoặc schema.
- Bản phân công `prompts/Phan_cong_Sprint3_Backend_Frontend.md` trùng nội dung
  `huongdan/Phan_cong_Sprint3.md` sau chuẩn hoá Markdown, chỉ thêm một chuỗi `agy`
  không có nghĩa ở dòng Buffer. Giữ một bản phân công tại `huongdan/`.
- Sửa 15 lỗi Ruff do upstream: import thừa/thứ tự import, dict literal,
  context manager, Decimal(0) và khai báo UTC của dữ liệu thời gian trong test.
  Giữ cách lưu UTC không kèm timezone đúng với model hiện tại.
- Cập nhật codebase map và hướng dẫn `huongdan/kiem_thu_sau_pull_main.md`.
- `backups/` vẫn không xuất hiện lại; nơi lưu dump là volume `postgres_backups`.

## Kiểm chứng

| Kiểm tra | Kết quả |
| --- | --- |
| Pytest toàn bộ sau pull và di chuyển | **350 passed**, 68,93 giây |
| Chạy lại các phần bị chỉnh sau sửa lint | **50 passed**, 7,72 giây |
| JavaScript | **25 passed** |
| Ruff | Đạt với `app tests alembic ../tests` |
| Mypy | Đạt, **43 file ứng dụng** |
| Git | HEAD khớp origin/main, không còn xung đột hoặc lỗi whitespace |
| Cấu trúc và Excel | Đủ 25 file Python trong `backend/tests`; SHA256 workbook giữ nguyên; không có `backend/app/tests` hoặc `backups/` |
| Build/khởi chạy Docker local | App và PostgreSQL healthy, simulator đang chạy |
| Đăng nhập HTTP local | Tài khoản mẫu admin và driver: **200** |
| Trang web qua HTTP | `/monitoring`, `/sessions`, `/sessions/anomalies`, `/audit`, `/sessions/mine`: **200** |
| API giám sát | Đủ **20 SIM- trụ online** |
| API phiên | Danh sách có **4 phiên** tại lúc kiểm tra; tài xế mẫu current trả **204** vì chưa có phiên mở |

Không thao tác nghiệm thu bố cục bằng trình duyệt, không chạy lại toàn bộ bộ
nghiệm thu Docker hoặc workflow GitHub. App local được giữ chạy để người dùng thử.

## Chức năng mới thực sự

Code từ main không thêm màn hình hoặc JS mới. T-37/T-38 tách handler của luồng
bắt đầu/dừng phiên đã có; T-36 và SCRUM-187 bổ sung bằng chứng kiểm thử.
API phiên hiện tại giảm truy vấn nhờ tải kèm hóa đơn. T-55 và 20 trụ cấu hình
được là thay đổi local trước đó, đã được giữ khi đồng bộ.

Sau báo cáo đồng bộ, người dùng yêu cầu bật cả các trụ trong ảnh giám sát:
T-55 đã mở rộng tuỳ chọn chạy 5 trụ mẫu và báo đủ đầu nối cho SIM.
Máy hiện chạy 25 trụ / 49 đầu nối; xem phần bổ sung trong `ketqua/T-55_ket_qua.md`.

## Gộp DANG-DAI theo yêu cầu tiếp theo — 06/10/2026

### Git, cấu trúc và xung đột

- Fetch nhánh `origin/DANG-DAI` tới `34a9b4d`; gộp vào main local bằng merge
  commit `55d58a7`. Không clone thêm bản sao, không push lên GitHub.
- Trước merge giữ toàn bộ thay đổi tracked/untracked trong stash
  `3834b9fb9f249b37c990e0c79f32cd259a54e65e`, đã áp dụng lại; stash vẫn giữ.
  Các thay đổi sắp xếp, T-55 và sửa bộ lọc tiếp tục nằm trong working tree.
- Giải quyết xung đột theo code hiện dùng: giữ tối ưu snapshot SSE, handler
  Start/Stop, quy tắc lint và toàn bộ test local; nhận login/AuthGuard của Đại.
- Giữ revision T-21 `h20261003_t21_ocpp_request_payload` đã dùng, bỏ migration
  merge-head trùng của nhánh. Chuỗi hiện tại có một head `h20261004_defaults`;
  không đổi revision đã áp dụng, không xóa database hoặc Docker volume.
- Di chuyển sáu test upstream chỉnh vào `backend/tests/unit/`, tài liệu mới vào
  `huongdan/` và `ketqua/`, bổ sung nhật ký đồng đội vào `ketqua/nhat_ky.md`.
  Không tạo lại `backend/app/tests`, root `scripts` hay `backups`.
- Đổi script kiểm chứng SCRUM-135 thành lệnh chạy bộ test với DB tạm. Bản gốc
  thử 5 mật khẩu sai vào localhost sẽ khóa IP 15 phút; bản local không gọi
  server đang chạy và không thực thi HTTP lúc import.
- Bật lại các test SCRUM-130/135 bị collect_ignore của nhánh bỏ qua; sửa ca
  kiểm tra login để đọc HTML đã render có URL tài nguyên gắn phiên bản.
- Giữ helper `asset_url`, nhúng context quyền và AuthGuard vào layout/login;
  giữ lọc theo trụ, đóng drawer và loại bỏ mock riêng của trang giám sát.
  Bổ sung kiểm thử chọn đầu nối và khóa nút login đến khi chuyển trang.

Fetch cũng thấy origin/main có `bde0d75` (Scrum 165) và `d084dea` (Scrum 166).
Hai commit này chưa nằm trong DANG-DAI và chưa gộp trong đợt này; phạm vi yêu cầu
là lấy nhánh DANG-DAI. Các kết luận dưới đây áp dụng working tree hiện tại.

### Task và mức hoàn thành theo code thực tế

| Task | Nhận được từ Đại | Đánh giá |
| --- | --- | --- |
| SCRUM-135 | Đăng nhập, toggle mật khẩu và báo lỗi đã có trước gộp. Nhánh chỉnh validation, kiểm tra quyền cho `next`, ApiClient xử lý 204/AbortSignal và thêm endpoint `/api/auth/me`. | Cải tiến phần đã có, không phải chức năng đăng nhập mới. Kiểm thử hành vi/API đạt. AuthGuard đang dùng context server; route_guard.js là helper chưa được template nạp. |
| SCRUM-190 (thuộc T-52/SCRUM-181) | Select đầu nối Available và nút Bắt đầu sạc trong chi tiết. | Giao diện thử chạy được; không gọi API start, không phát RemoteStartTransaction, không tạo phiên. |
| SCRUM-191 | Map/timer đếm ngược nhưng không có code đưa yêu cầu vào Map. | Chưa có đường chạy trạng thái chờ; không reintroduce timer chưa dùng. |
| SCRUM-192 | Không có đường xử lý phản hồi từ chối/bận/timeout. | Chưa hoàn thành. |
| SCRUM-194 | Không có bằng chứng kiểm thử bắt đầu sạc đầu cuối. | Chưa hoàn thành; kiểm thử UI prototype không thay thế nghiệm thu full flow. |

Chưa thể đánh dấu T-52 Done. API T-51/SCRUM-193 và phần phản hồi vẫn là phần
phụ thuộc. Không triển khai thêm RemoteStart/RemoteStop hoặc T-56/SCRUM-185.

### Kiểm chứng sau gộp

| Kiểm tra | Kết quả |
| --- | --- |
| Pytest toàn bộ (không bỏ qua các test SCRUM-130/135) | **390 passed**, 26 warnings, 66,58 giây |
| Node kiểm thử JS được phát hành | **47 passed**, không fail/skip |
| Ruff / Mypy | Đạt; Mypy **43 file** |
| Alembic | Một head `h20261004_defaults`; app khởi động/upgrade thành công |
| Build Docker local | App và PostgreSQL healthy; simulator đang chạy |
| HTTP + DOM trên HTML và JS thực tế | **44 kiểm tra đạt**: 5 vai trò login/me/trang chính; 25 online/49 đầu nối; lỗi/maintenance/ready filter; đóng drawer; start preview; SSE offline vô hiệu đầu nối; logout |
| Dữ liệu | Excel SHA256 giữ nguyên `C106E9B5E8458F2F02EF00604BDDED75882E9CFAF4D60C32EECCF2837471BA30`; giữ `.env` và volume PostgreSQL |
| Git | Không unmerged path hoặc conflict marker; diff whitespace đạt; stash an toàn vẫn giữ |

Trình duyệt tích hợp đã bị chặn `ERR_BLOCKED_BY_CLIENT` với localhost; kiểm tra
giao diện dùng DOM emulation (jsdom), không khẳng định đã nghiệm thu bố cục trực
quan. Không chạy workflow GitHub. App local được giữ ở <http://localhost:8000>.

### Đính chính và gỡ mock đăng nhập — 06/10/2026

Người dùng chỉ ra đăng nhập và hiện/ẩn mật khẩu đã có trước khi gộp. Đối chiếu
với `bff0369` xác nhận hai chức năng này có sẵn; thông tin trước đó mô tả chúng
là chức năng mới không chính xác. Bảng task và hướng dẫn đã sửa theo thay đổi
thực tế, không lấy số lượng test đạt để suy ra có thêm chức năng.

Đã gỡ `login-mock-notice`, tham số chọn chế độ mock, hàm `mockLogin` và ba mật
khẩu điều khiển `success/wrong/locked` khỏi code đăng nhập. Mọi lần submit hợp
lệ đều gọi `/api/auth/login`; URL cũ `?mock=1` không chuyển sang luồng giả.
Giữ đăng nhập bằng tài khoản trong database, tạo cookie phiên, xử lý lỗi và
hiện/ẩn mật khẩu theo yêu cầu S-02/T-05. Simulator OCPP vẫn dùng để thay thiết
bị phần cứng như phạm vi dự án đã thống nhất.

Đoạn mock từ nhánh có thuộc tính `hidden`, nhưng CSS `.alert` đặt `display:flex`
ghi đè cách ẩn mặc định; vì vậy dòng hướng dẫn có thể hiện ngay cả ở `/login`.
Đã xóa hẳn đoạn này thay vì chỉ ẩn bằng CSS.

Sau gỡ: **48 kiểm thử JS** và **43 kiểm thử Python** (auth, SCRUM-135,
frontend assets) đạt; Ruff và diff whitespace đạt. **24 kiểm tra HTTP/DOM**
trên app local đạt với cả `/login` và `/login?mock=1`: không có banner/mock
logic, nút mắt hoạt động, mật khẩu `success` phải qua API, lỗi hiển thị theo API,
tài khoản admin hợp lệ tạo cookie phiên. DOM emulation không hỗ trợ điều hướng;
chuyển trang được kiểm chứng bằng kiểm thử JS với location spy.

## Gộp code mới và sửa CI/CD trên f — 06/10/2026

- Fetch `origin/f` tại `a47c491f611f430bce43b220a5d498b316132d6b`;
  code `ghi_nhat_ky` đã được giữ trong merge `11aa36b`. Không ghi đè lịch sử
  nhánh hoặc force-push. Gộp thêm `origin/main` tại `717cc62` với MeterValues
  T-40/T-41 và giao diện phiên T-48/T-50, giữ các sửa lỗi local trước đó.
- GitHub run `37432097816` trên f thất bại vì 15 lỗi Ruff; các run CI/CD
  `37435549566`/`37435549518` trên main thất bại vì 34 lỗi Ruff. Bản gộp đã
  sửa import, kiểu dữ liệu và các lỗi lint, vẫn chạy đủ kiểm tra hiện có.
- Sửa ba test MeterValues gọi handler trực tiếp: commit giao dịch như dispatcher
  trước khi đọc dữ liệu, vì fixture tắt autoflush. Không bỏ test hoặc nới assertion.
- Migration mới nối sau `h20261004_defaults`, giữ bảng/số đo hiện có và điều
  chỉnh foreign key/index. Kiểm tra upgrade/downgrade SQLite và PostgreSQL đạt.
- Gỡ mock riêng của trang phiên từ upstream. API rỗng/lỗi không sinh phiên mẫu,
  kWh lấy từ API/SSE. Báo cáo T-48/T-50 phân biệt kết quả tác giả upstream với
  bằng chứng kiểm tra sau gộp, không suy ra nghiệm thu đầy đủ từ CI.
- CD chạy job kiểm tra khi push f; job triển khai chỉ chạy trên main/master,
  có test chống triển khai từ f và chống bỏ qua lỗi kiểm tra. Chưa có staging
  thật để nghiệm thu SSH deploy; không đánh đồng workflow xanh với đã triển khai.

### Kiểm chứng trước push

| Kiểm tra | Kết quả |
| --- | --- |
| Linux/Python 3.11, nguồn từ Git index, đúng quyền file Git | **405 passed**, coverage nhánh/dòng tổng hợp **71%**, 64,78 giây |
| Ruff / Mypy / pip-audit trong Linux | Đạt; Mypy **45 file**; không có lỗ hổng thư viện được báo |
| Hành vi JavaScript | **51 passed**, không fail/skip |
| Docker image từ code hiện tại | Build đạt |
| Nghiệm thu Compose/PostgreSQL/OCPP | 8/9 đạt trong lượt đầy đủ; ca stop/start simulator đạt cả 3 vòng khi chạy lại riêng sau khi dừng lượt kiểm thử bị chồng |
| Phạm vi dữ liệu | Chỉ dọn project Compose nghiệm thu tạm; giữ volume PostgreSQL thật và `.env` |
| Excel | SHA256 vẫn `C106E9B5E8458F2F02EF00604BDDED75882E9CFAF4D60C32EECCF2837471BA30` |

Snapshot trước khi hoàn tất merge vẫn giữ trong Git stash `257d1cd`.
Kết quả GitHub phải đọc từ workflow của commit được push lên f sau bước này.
