# Quy chuẩn code — CSMS (dùng cho cả người và AI vide code)

Mục tiêu: khi bạn hoặc AI sinh code, **luôn có một cách duy nhất đúng** để làm mỗi
việc, để không lệch nhau giữa các lần sinh code và không phình file/thư mục.

---

## 1. Nguyên tắc chung (áp dụng mọi ngôn ngữ)

| # | Quy tắc | Nguồn |
| --- | --- | --- |
| 1 | Không hardcode bí mật (DB URL, API key, webhook secret) — luôn qua biến môi trường, đọc ở đúng 1 nơi | lặp lại ở hầu hết NFR |
| 2 | Không log: mật khẩu, token, mã thẻ đầy đủ (chỉ 4 ký tự cuối), thông tin thanh toán, PII | S-15 NFR, DoD |
| 3 | Bảng ghi log/sổ cái/nhật ký (`audit_logs`, `ledger_entries`, `ocpp_messages`) **chỉ được INSERT** — cấp quyền DB chặn UPDATE/DELETE từ tài khoản ứng dụng | T-57, S-41 |
| 4 | Tiền lưu bằng **số nguyên (đồng)**, không dùng số thực | S-28 NFR |
| 5 | Mọi khoảng thời gian/ngưỡng (nhịp tim, timeout, số ngày giữ log...) là **tham số cấu hình**, không ghi cứng | T-17, T-31, S-25 |
| 6 | Job nền chạy 2 lần liên tiếp không được gây tác dụng phụ khác nhau (idempotent) | DoD |
| 7 | Một tin nhắn/webhook xử lý 2 lần phải cho kết quả **giống hệt** xử lý 1 lần — chống trùng lưu ở DB, không lưu ở biến trong tiến trình | R-03, S-14, S-39, S-49 |
| 8 | Mặc định từ chối (deny-by-default) với mọi route chưa khai quyền rõ ràng | T-06 |

---

## 2. Backend — Python / FastAPI

### 2.1 Layer nào làm việc gì (không được lẫn)

```
router  -> chỉ: parse request, gọi Depends kiểm quyền, gọi 1 service, trả response
service -> toàn bộ logic nghiệp vụ, transaction DB
model   -> chỉ định nghĩa bảng (SQLAlchemy), KHÔNG chứa logic nghiệp vụ
schema  -> chỉ định nghĩa hình dạng dữ liệu vào/ra (Pydantic)
ocpp/handlers -> tương đương "router" nhưng cho message OCPP thay vì HTTP
```

Nếu thấy một router có `if/else` nghiệp vụ dài hơn ~10 dòng → chuyển vào service.
Nếu thấy một model có method tính toán phức tạp → chuyển vào `services/`.

### 2.2 Quy ước đặt tên

- File & biến: `snake_case`. Class: `PascalCase`. Hằng số: `UPPER_SNAKE_CASE`.
- Bảng DB: số nhiều, `snake_case` (`charging_sessions`, không phải `ChargingSession`).
- Cột: khoá chính luôn là `id`; thời điểm tạo/sửa luôn `created_at`/`updated_at`
  (mẫu bắt buộc từ T-01, mọi migration sau phải theo).
- Router prefix theo epic, không theo REST resource đơn thuần khi nghiệp vụ phức
  tạp hơn CRUD (ví dụ `/sessions/remote-stop`, không nhét vào `PATCH /sessions/{id}`).
- Một handler OCPP = một hàm `async def handle_<action_snake_case>(...)`, file
  cùng tên (`start_transaction.py` → `handle_start_transaction`).

### 2.3 Giới hạn kích thước (chặn "vượt giới hạn" khi vide code)

| Loại file | Số dòng tối đa gợi ý | Khi vượt → làm gì |
| --- | --- | --- |
| Router | 150 | Tách theo epic con, không thêm route "tiện tay" vào router khác |
| Handler OCPP | 150 | Phần chung (validate khung, log) đẩy vào `ocpp/dispatcher.py`, không lặp lại trong từng handler |
| Service | 250 | Tách theo domain con (ví dụ `billing/segment_split.py` tách khỏi `billing/invoice.py`) |
| Model | 100 mỗi bảng | Bảng phức tạp hơn → tách file riêng, không gộp 5 bảng vào 1 file "models.py" |
| Test file | không giới hạn cứng, nhưng 1 file test = 1 đơn vị được test | Test theo bảng dữ liệu (table-driven), theo mẫu T-15 |

Nếu một PR làm 1 file vượt quá 1.5x giới hạn trên → bắt buộc refactor tách file
trước khi merge, không "để sau".

### 2.4 Transaction & tính đúng đắn (rất quan trọng với domain này)

- Chuỗi thao tác phải nguyên tử trong **một transaction DB** khi:
  - tra bảng chống trùng + gọi handler (T-30)
  - đọc/ghi số đo mới nhất để so mốc thời gian (T-42)
  - trừ ví + lập hoá đơn (S-37: *"không bao giờ bị trừ hai lần"*)
- Hàm tính toán **thuần (pure function)**, không đọc DB, cho các phần:
  - `energy_calc.py` (kWh = số đo cuối − số đo đầu)
  - `segment_split.py` (chia đoạn theo khung giờ) — bắt buộc theo S-30 NFR, để
    test theo bảng dữ liệu không phụ thuộc DB
- Làm tròn tiền: quy tắc khai báo **ở đúng một chỗ** (ví dụ
  `services/billing/rounding.py`), mọi nơi khác gọi vào, không tự làm tròn tại
  chỗ (S-05 NFR).

### 2.5 Test bắt buộc theo loại thay đổi (khớp DoD)

| Thay đổi loại gì | Bắt buộc kèm theo |
| --- | --- |
| Bất kỳ logic mới | unit test |
| Đụng vào tiền | bộ ca kiểm thử với **đáp án tính tay**, lưu ở `hardware/app/tests/billing_truth_table/`, có tên người tính + ngày |
| Đụng vào xử lý tin nhắn OCPP | test "xử lý 2 lần = xử lý 1 lần" |
| Thêm job nền | test "chạy job 2 lần liên tiếp không đổi thêm gì" |
| Đụng luồng kết nối/mất kết nối trụ | chạy qua kịch bản trong `hardware/app/dev_tools/ocpp_simulator/scenarios/` (`hardware/app/tests/ocpp_scenarios/`), không chỉ unit test |

### 2.6 Dependencies

- Không thêm package mới vào `requirements.txt` mà không ghi lý do trong PR.
- Không cài package trùng chức năng với package đã có (ví dụ đã có `httpx` thì
  không thêm `requests`).

---

## 3. Frontend — HTML / CSS (+ JS thuần)

### 3.1 Nguyên tắc

- **Server-rendered trước, JS chỉ để realtime/UX nhỏ.** Không biến trang thành
  SPA. Dữ liệu ban đầu render sẵn từ Jinja2, JS chỉ cập nhật phần đổi động (số
  kWh, trạng thái đầu nối...) qua SSE.
- Mọi trang **extends `base.html`** — không copy `<head>`, không tự thêm
  `<link>`/`<script>` trùng những gì `base.html` đã có.
- Class CSS đặt tên theo BEM đơn giản: `.card`, `.card__title`,
  `.card--offline`. Không dùng class 1 lần dùng 1 nơi kiểu `.abc123`.

### 3.2 Giới hạn kích thước

| Loại file | Giới hạn gợi ý |
| --- | --- |
| 1 template `.html` | ~150 dòng — nếu dài hơn, tách `{% include %}` cho phần lặp lại (ví dụ 1 ô trụ trong lưới T-24) |
| 1 file CSS trang riêng | ~80 dòng — phần lớn style nên nằm ở `components.css` dùng chung |
| 1 file JS trang riêng | ~100 dòng — logic dùng lại (SSE, gọi API, chặn double-submit) luôn nằm ở file dùng chung trong `static/js/` |

### 3.3 Bắt buộc cho mọi trang có form

- Chặn bấm lưu 2 lần liên tiếp (`form_guard.js` — yêu cầu lặp lại ở T-09, T-11,
  S-04 AC cuối).
- Lỗi hiển thị **tại đúng ô nhập**, không hiện alert chung chung.
- Validate ở client **và** validate lại ở server — server luôn là nơi quyết định
  cuối cùng (T-11 NFR: *"không tin kết quả kiểm ở trình duyệt"*).

### 3.4 Accessibility bắt buộc (không phải tuỳ chọn)

- Trạng thái luôn có nhãn chữ đi kèm màu (không dùng màu làm kênh thông tin
  duy nhất).
- Mọi màn hình phải dùng được ở chiều rộng **360px**.

---

## 4. Quy trình khi dùng AI để vide code (checklist trước khi chấp nhận code AI sinh)

1. File AI vừa tạo có nằm đúng vị trí trong `01_CODEBASE_MAP.md` không?
2. File có vượt giới hạn dòng ở mục 2.3 / 3.2 không? Nếu có → yêu cầu tách trước
   khi nhận.
3. Có secret nào bị hardcode không?
4. Có log nào in mật khẩu/token/mã thẻ đầy đủ/PII không?
5. Nếu đụng tới OCPP message hoặc webhook: có xử lý chống trùng ở DB chưa (không
   phải biến trong RAM)?
6. Nếu đụng tới tiền: có test đối chiếu đáp án tính tay chưa?
7. Có README/biến môi trường mới cần cập nhật không?

Nếu một câu trả lời "không" ở trên → **chưa merge**, quay lại yêu cầu AI sửa
đúng phạm vi đó, không yêu cầu "viết lại từ đầu" (dễ sinh thêm file rác).
