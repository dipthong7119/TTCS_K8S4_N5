# KẾ HOẠCH LÀM VIỆC CHI TIẾT: SCRUM-90 (SPRINT 6) — HOÀNG VĂN ĐỨC

* **Họ và tên**: Hoàng Văn Đức
* **Vai trò**: Backend Developer
* **Epic phụ trách**: Giám sát vận hành (*Operational Monitoring*)
* **Nhiệm vụ trọng tâm**: **SCRUM-90** — *Cảnh báo khi trụ ngoại tuyến quá lâu hoặc báo lỗi liên tục* (3 SP)
* **Nhánh Git làm việc**: `feature/SCRUM-90-canh-bao-offline-va-loi`
* **Người phối hợp Frontend (subtask FE)**: Phạm Văn Tuấn
* **Người Reviewer / QA chéo**: Ngô Quang Tùng (Quang Tùng kiểm thử & review Đức; Đức review Tạ Như Vinh)
* **Căn cứ kế hoạch**:
  - Phân công Sprint 678: [`prompts/phan-cong-sprint-678.md`](file:///d:/TTCS_K8S4_N5/prompts/phan-cong-sprint-678.md)
  - Quy tắc Agent: [`prompts/00_QUY_TAC_AGENT.md`](file:///d:/TTCS_K8S4_N5/prompts/00_QUY_TAC_AGENT.md)
  - Codebase Map: [`prompts/01_CODEBASE_MAP.md`](file:///d:/TTCS_K8S4_N5/prompts/01_CODEBASE_MAP.md)
  - Đặc tả yêu cầu: Story S-46 tại [`prompts/02_DAC_TA_DU_AN.md`](file:///d:/TTCS_K8S4_N5/prompts/02_DAC_TA_DU_AN.md#L1186)

---

## 1. MỤC TIÊU VÀ PHẠM VI NGHIỆP VỤ

### 1.1. Story gốc: S-46 (Sprint 6, 3 SP)
* **User Story**: Là vận hành viên tôi muốn được báo khi trụ hỏng để cử người đi sửa trước khi khách phàn nàn.
* **Tiêu chuẩn nghiệm thu (Acceptance Criteria - Given/When/Then)**:
  1. **AC1 — Cảnh báo trụ ngoại tuyến quá lâu**: Giả sử một trụ không gửi nhịp tim/tin nhắn quá ngưỡng cấu hình (`CHARGE_POINT_OFFLINE_ALERT_MINUTES`), Khi hệ thống quét kiểm tra, Thì tự động sinh một cảnh báo loại `offline` với trạng thái `active`.
  2. **AC2 — Cảnh báo lỗi đầu nối liên tục**: Giả sử một đầu nối ghi nhận $\ge N$ lỗi (`CONNECTOR_ERROR_ALERT_THRESHOLD`) trong bảng `connector_errors` trong khoảng thời gian cửa sổ trượt $T$ phút, Khi hệ thống kiểm tra, Thì tự động sinh một cảnh báo loại `connector_error` với trạng thái `active`.
  3. **AC3 — Chống spam / Cooldown (Deduplication)**: Cùng một trụ sạc / đầu nối, nếu đã tồn tại một cảnh báo đang có trạng thái `active`, Thì hệ thống **tuyệt đối không** sinh thêm cảnh báo mới cho đến khi cảnh báo cũ được đóng (`resolved`).
  4. **AC4 — Hiển thị và Thông báo**: Cung cấp API để Frontend (Phạm Văn Tuấn) hiển thị danh sách cảnh báo nổi bật ở đầu trang theo dõi vận hành; ghi nhận thông báo gửi đi (log/mock email theo kiến trúc hiện tại).
  5. **AC5 — Đóng cảnh báo (Resolve)**: Cung cấp API cho vận hành viên/quản trị viên xác nhận và đóng cảnh báo (`resolved`), kèm ghi nhận thời gian và người đóng.

---

## 2. THIẾT KẾ KỸ THUẬT VÀ RÀNG BUỘC KIẾN TRÚC

Tuân thủ nghiêm ngặt các ranh giới tại [`prompts/00_QUY_TAC_AGENT.md`](file:///d:/TTCS_K8S4_N5/prompts/00_QUY_TAC_AGENT.md):

### 2.1. Cấu trúc CSDL & Alembic Migration
* **Tạo bảng mới `alerts`** qua migration Alembic (không sửa chay model):
  - `id`: Integer, Primary Key, Autoincrement.
  - `charge_point_id`: Integer, ForeignKey(`charge_points.id`), Index, Not Null.
  - `connector_id`: Integer, ForeignKey(`connectors.id`), Nullable (nếu lỗi toàn trụ thì null).
  - `alert_type`: String(50), Not Null (`offline` hoặc `connector_error`).
  - `severity`: String(20), Default `'warning'` (`warning`, `critical`).
  - `status`: String(20), Default `'active'` (`active`, `resolved`).
  - `message`: Text, Not Null (mô tả chi tiết nguyên nhân, số lỗi đếm được hoặc thời gian offline).
  - `error_count`: Integer, Nullable (số lỗi đếm được tại thời điểm kích hoạt).
  - `triggered_at`: DateTime(timezone=True), Not Null (mốc thời gian phát hiện).
  - `resolved_at`: DateTime(timezone=True), Nullable.
  - `resolved_by_id`: Integer, ForeignKey(`users.id`), Nullable.
* **Chỉ mục chống trùng (Index)**:
  - `ix_alerts_cp_status_type`: Index trên `(charge_point_id, status, alert_type)` để câu lệnh kiểm tra tồn tại chạy cực nhanh và đảm bảo tính nhất quán.

### 2.2. Cấu hình hệ thống ([backend/app/config.py](file:///d:/TTCS_K8S4_N5/backend/app/config.py))
Tất cả biến môi trường cấu hình ngưỡng được tập trung tại `config.py` (không rải `os.getenv`):
* `ALERT_OFFLINE_THRESHOLD_MINUTES`: Thời gian trụ ngoại tuyến để báo động (mặc định: `15` phút).
* `ALERT_ERROR_COUNT_THRESHOLD`: Số lỗi tối thiểu để báo động (mặc định: `3` lỗi).
* `ALERT_ERROR_WINDOW_MINUTES`: Cửa sổ thời gian đếm lỗi (mặc định: `10` phút).

### 2.3. Tầng Service & Logic nghiệp vụ ([backend/app/services/alert_service.py](file:///d:/TTCS_K8S4_N5/backend/app/services/alert_service.py))
* `check_and_generate_offline_alerts(db)`: Truy vấn các trụ có `status == 'Offline'` hoặc `last_heartbeat_at` vượt quá ngưỡng; kiểm tra nếu chưa có alert `active` cùng loại trên trụ thì chèn mới.
* `check_and_generate_connector_error_alerts(db)`: Truy vấn bảng `connector_errors` với cửa sổ thời gian gần nhất; nhóm theo đầu nối/trụ; nếu vượt ngưỡng và chưa có alert `active` thì chèn mới.
* `resolve_alert(db, alert_id, resolved_by_id)`: Đóng cảnh báo, cập nhật `status = 'resolved'`, `resolved_at = datetime.now(timezone.utc)`.
* `get_active_alerts(db, skip, limit)`: Lấy danh sách cảnh báo đang kích hoạt.

### 2.4. Tầng Router REST API ([backend/app/routers/alerts.py](file:///d:/TTCS_K8S4_N5/backend/app/routers/alerts.py))
Phân quyền theo vai trò (`admin`, `operator`):
* `GET /api/alerts`: Lấy danh sách cảnh báo (hỗ trợ query `status`, `charge_point_id`, `skip`, `limit`).
* `POST /api/alerts/{alert_id}/resolve`: Vận hành viên/Admin đóng cảnh báo.
* `POST /api/alerts/scan`: Trigger thủ công job quét cảnh báo (dành cho admin/job định kỳ).

---

## 3. LỘ TRÌNH THỰC HIỆN CHI TIẾT (TỪNG BƯỚC)

### Bước 1: Tạo nhánh & Khởi tạo CSDL
- Tạo nhánh Git: `feature/SCRUM-90-canh-bao-offline-va-loi`.
- Khai báo model `Alert` tại `backend/app/models/alert.py` và đăng ký trong `backend/app/models/__init__.py`.
- Tạo migration Alembic `alembic revision --autogenerate -m "create_alerts_table"`.
- Bổ sung cấu hình ngưỡng vào `backend/app/config.py`.

### Bước 2: Xây dựng Service kiểm tra cảnh báo
- Viết `backend/app/services/alert_service.py`.
- Đảm bảo tính **Idempotency & Deduplication**: Quét 2 lần liên tiếp không sinh 2 dòng cảnh báo cho cùng một trụ/lỗi đang mở.
- Mock/Log gửi thông báo: Ghi log cảnh báo mức WARNING/CRITICAL chuẩn bị cho việc tích hợp email sender.

### Bước 3: Xây dựng API Router & Schema Pydantic
- Schema tại `backend/app/schemas/alert.py`: `AlertResponse`, `AlertResolveRequest`.
- Router tại `backend/app/routers/alerts.py` và đăng ký vào `backend/app/main.py`.
- Áp dụng phân quyền: Chỉ vai trò `admin` và `operator` mới có quyền xem và đóng cảnh báo (chặn các vai trò khác theo quy tắc deny-by-default).

### Bước 4: Viết Unit Test chuyên biệt ([backend/tests/unit/test_alerts.py](file:///d:/TTCS_K8S4_N5/backend/tests/unit/test_alerts.py))
Bao phủ 100% các kịch bản AC:
1. `test_offline_alert_triggered`: Trụ offline quá hạn tạo đúng 1 alert `active`.
2. `test_offline_alert_not_triggered_if_online`: Trụ hoạt động bình thường không sinh alert.
3. `test_deduplication_offline`: Quét nhiều lần liên tiếp không sinh alert trùng nếu alert cũ chưa resolve.
4. `test_connector_error_alert_threshold`: Đủ $\ge 3$ lỗi trong 10 phút tạo 1 alert; dưới 3 lỗi không tạo.
5. `test_resolve_alert_success`: Đóng alert thành công, cập nhật `resolved_at` và `resolved_by_id`.
6. `test_new_alert_allowed_after_resolved`: Sau khi alert cũ đã `resolved`, sự cố mới phát sinh tiếp tục tạo alert mới.
7. `test_permission_deny_by_default`: Tài xế hoặc người dùng chưa xác thực bị từ chối truy cập (401/403).

### Bước 5: Tài liệu Hợp đồng API & Bàn giao
- Xuất bản tài liệu Hợp đồng API tại `ketqua/SCRUM-90_hop_dong_api.md` chuyển giao cho **Phạm Văn Tuấn** (Frontend).
- Kiểm tra linter `ruff check` và `pytest` chạy xanh 100%.
- Cập nhật nhật ký công việc tại `ketqua/nhat_ky.md`.
- Gửi yêu cầu review chéo [QA] cho **Ngô Quang Tùng**.

---

## 4. MA TRẬN PHỐI HỢP VÀ BÀN GIAO

| Đối tác | Nội dung phối hợp | Trách nhiệm của Hoàng Văn Đức |
|---|---|---|
| **Phạm Văn Tuấn** (Frontend) | Tích hợp giao diện cảnh báo đầu màn hình giám sát | Bàn giao Hợp đồng API (`GET /api/alerts`, `POST /api/alerts/{id}/resolve`) kèm mock data |
| **Ngô Quang Tùng** (Backend Reviewer / QA) | Duyệt PR & kiểm thử nghiệm thu chéo subtask `[QA]` | Cung cấp tài liệu kịch bản kiểm thử và bộ Unit Test đạt 100% pass |
| **Tạ Như Vinh** (Backend) | Đức thực hiện review chéo công việc của Vinh (SCRUM-86, 87, 88) | Đọc PR, kiểm tra code và logic tính toán đối soát của Vinh |

---

## 5. CHECKLIST ĐỊNH NGHĨA HOÀN THÀNH (Definition of Done - DoD)

- [x] Code nằm đúng vị trí theo [`prompts/01_CODEBASE_MAP.md`](file:///d:/TTCS_K8S4_N5/prompts/01_CODEBASE_MAP.md).
- [x] Schema CSDL có migration Alembic đầy đủ, nâng/hạ cấp không lỗi (`h20261013_alerts`).
- [x] Logic chống trùng lặp chạy an toàn ở DB query, chạy lặp lại không tác dụng phụ.
- [x] Phân quyền chặt chẽ, deny-by-default.
- [x] Bộ 17 unit test độc lập, chạy sạch 100% (`test_alerts.py`).
- [x] Linter ruff kiểm tra không có cảnh báo.
- [x] Hợp đồng API bàn giao cho FE rõ ràng (`SCRUM-90_hop_dong_api.md`).
