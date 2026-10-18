# KẾ HOẠCH LÀM VIỆC CHI TIẾT: SCRUM-92 (SPRINT 8) — HOÀNG VĂN ĐỨC

* **Họ và tên**: Hoàng Văn Đức
* **Vai trò**: Backend Developer
* **Epic phụ trách**: Giám sát vận hành (*Operational Monitoring*)
* **Nhiệm vụ trọng tâm**: **SCRUM-92** — *Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển* (3 SP)
* **Story gốc trong đặc tả**: [S-57](file:///d:/TTCS_K8S4_N5/prompts/02_DAC_TA_DU_AN.md#L1204)
* **Nhánh Git làm việc**: `feature/SCRUM-92-xoa-du-lieu-ca-nhan`
* **Người phối hợp Frontend (subtask FE)**: Phạm Văn Tuấn (Giám sát vận hành 90–92, giao diện yêu cầu và quản trị xóa dữ liệu)
* **Người Reviewer / QA chéo**: Ngô Quang Tùng (Quang Tùng kiểm thử & review Đức; Đức review Tạ Như Vinh)
* **Căn cứ kế hoạch**:
  - Phân công Sprint 678: [`prompts/phan-cong-sprint-678.md`](file:///d:/TTCS_K8S4_N5/prompts/phan-cong-sprint-678.md)
  - Quy tắc Agent: [`prompts/00_QUY_TAC_AGENT.md`](file:///d:/TTCS_K8S4_N5/prompts/00_QUY_TAC_AGENT.md) (Quy tắc 47 về Nghị định 13/2023/NĐ-CP và phạm vi dữ liệu)
  - Codebase Map: [`prompts/01_CODEBASE_MAP.md`](file:///d:/TTCS_K8S4_N5/prompts/01_CODEBASE_MAP.md)
  - Đặc tả yêu cầu: Story S-57 tại [`prompts/02_DAC_TA_DU_AN.md`](file:///d:/TTCS_K8S4_N5/prompts/02_DAC_TA_DU_AN.md#L1204)

---

## 1. MỤC TIÊU VÀ TIÊU CHUẨN NGHIỆM THU (ACCEPTANCE CRITERIA)

### 1.1. Story S-57 (Sprint 8, 3 SP)
* **User Story**: Là tài xế tôi muốn yêu cầu xoá thông tin cá nhân và lịch sử sạc của mình để thực hiện quyền theo Nghị định 13/2023/NĐ-CP.
* **Tiêu chuẩn nghiệm thu (Acceptance Criteria - Given/When/Then)**:
  1. **AC1 — Gửi yêu cầu xóa dữ liệu cá nhân (`POST /api/privacy/erasure-requests`)**:
     - Tài xế có thể gửi yêu cầu xóa dữ liệu cá nhân và lịch sử di chuyển kèm lý do.
     - Hệ thống kiểm tra điều kiện tiên quyết:
       + Không có phiên sạc đang hoạt động (`active`).
       + Không có đặt chỗ đang hoạt động (`pending` hoặc `accepted`).
       + Ví không còn số dư dương (`balance_vnd == 0`). Nếu còn số dư, từ chối với thông báo hướng dẫn hoàn tiền hoặc rút tiền trước khi xóa.
       + Chống trùng lặp (idempotency): Không cho tạo trùng khi đã có yêu cầu ở trạng thái `pending`.
     - Lưu yêu cầu vào CSDL với trạng thái `pending` và ghi nhận nhật ký kiểm toán `privacy.request_created`.
  2. **AC2 — Tra cứu trạng thái yêu cầu (`GET /api/privacy/erasure-requests/my` & `GET /api/privacy/admin/erasure-requests`)**:
     - Tài xế tra cứu được trạng thái các yêu cầu của chính mình.
     - Quản trị viên (`admin`, `operator`) tra cứu được danh sách tất cả các yêu cầu, hỗ trợ lọc theo trạng thái (`pending`, `approved`, `rejected`), theo `driver_id` và phân trang.
  3. **AC3 — Phê duyệt và thực hiện ẩn danh hóa không thể đảo ngược (`POST /api/privacy/admin/erasure-requests/{id}/approve`)**:
     - Chỉ quản trị viên (`admin`) được quyền phê duyệt và thực hiện.
     - Kiểm tra lại điều kiện ví số dư (`balance_vnd == 0`) và phiên sạc hoạt động.
     - **Thực thi ẩn danh hóa bảo toàn số liệu kế toán/doanh thu**:
       + **Phiên sạc (`charging_sessions`)**: Chuyển `user_id = NULL`, `driver_name = 'ANONYMIZED'`, `id_tag = NULL`, `id_tag_id = NULL`. Toàn bộ dữ liệu trạm, trụ, thời gian, số đo kWh, doanh thu trạm và hóa đơn vẫn bảo toàn 100% phục vụ đối soát.
       + **Thẻ RFID (`id_tags`)**: Khóa thẻ (`is_blocked = True`), đổi mã thẻ thành `ANON_{id}_{hash}` để không tái sử dụng.
       + **Đặt chỗ (`reservations`)**: Ẩn danh hóa `id_tag = 'ANONYMOUS'`, hủy liên kết thẻ.
       + **Tài khoản người dùng (`users`)**: Vô hiệu hóa (`is_active = False`), đổi tên thành `'Người dùng ẩn danh'`, đổi email thành `anonymized_{id}_{hash}@privacy.local`, xóa mật khẩu (`password_hash = 'ANONYMIZED_ACCOUNT_DELETED'`).
       + **Sổ cái ví (`wallet_ledger`)**: Giữ nguyên toàn bộ bút toán bất biến (append-only), không chỉnh sửa hay xóa bất kỳ dòng nào.
     - Cập nhật trạng thái yêu cầu thành `approved`, ghi nhận người duyệt, thời gian duyệt và ghi nhật ký kiểm toán `privacy.request_approved`.
  4. **AC4 — Từ chối yêu cầu (`POST /api/privacy/admin/erasure-requests/{id}/reject`)**:
     - Quản trị viên từ chối yêu cầu và bắt buộc phải nhập lý do từ chối (`rejection_reason`).
     - Chuyển trạng thái yêu cầu thành `rejected`, ghi nhận thời gian và ghi nhật ký kiểm toán `privacy.request_rejected`.
  5. **AC5 — Phân quyền & Giới hạn pháp lý (Deny-by-default & NĐ 13/2023/NĐ-CP)**:
     - Endpoint tài xế chỉ cho phép vai trò `driver` truy cập và chỉ thao tác trên dữ liệu của chính mình.
     - Endpoint quản trị yêu cầu quyền `admin` (phê duyệt/từ chối) hoặc `operator` (xem danh sách). Chưa đăng nhập trả 401; sai quyền trả 403.

---

## 2. THIẾT KẾ KỸ THUẬT VÀ RÀNG BUỘC KIẾN TRÚC

### 2.1. CSDL & Migration Alembic
* Tạo bảng `data_erasure_requests`:
  - `id`: Integer, Primary Key.
  - `user_id`: Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True.
  - `status`: String(20), nullable=False, default="pending".
  - `request_reason`: String(500), nullable=True.
  - `rejection_reason`: String(500), nullable=True.
  - `requested_at`: DateTime, nullable=False, server_default=func.now().
  - `processed_at`: DateTime, nullable=True.
  - `processed_by`: Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True.
  - `created_at`, `updated_at`: DateTime, server_default=func.now().
  - Ràng buộc: `CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_data_erasure_requests_status")`.
  - Chỉ mục: `ix_data_erasure_requests_user_status` trên `(user_id, status)`.
* Migration Alembic: `h20261018_scrum92_data_erasure.py` kế thừa và hợp nhất 2 head hiện tại (`h20261016_integrate_feature_heads`, `4591d08fb87f`), giúp đồ thị Alembic quy về đúng 1 head duy nhất.

### 2.2. Tầng Service Nghiệp vụ (`backend/app/services/privacy_service.py`)
* `create_erasure_request(db, driver, reason)`: Kiểm tra điều kiện ví, phiên sạc, đặt chỗ, chống trùng, tạo yêu cầu và ghi audit log.
* `get_my_erasure_requests(db, driver_id)`: Danh sách yêu cầu của tài xế.
* `list_erasure_requests(db, status, driver_id, skip, limit)`: Tra cứu yêu cầu cho quản trị viên.
* `approve_erasure_request(db, request_id, admin_user)`: Thực thi quy trình ẩn danh hóa toàn diện, cập nhật trạng thái và ghi audit log.
* `reject_erasure_request(db, request_id, admin_user, rejection_reason)`: Từ chối yêu cầu và ghi audit log.

### 2.3. Tầng Router REST API (`backend/app/routers/privacy.py`)
* `POST /api/privacy/erasure-requests` (Role: `driver`)
* `GET /api/privacy/erasure-requests/my` (Role: `driver`)
* `GET /api/privacy/admin/erasure-requests` (Role: `admin`, `operator`)
* `POST /api/privacy/admin/erasure-requests/{id}/approve` (Role: `admin`)
* `POST /api/privacy/admin/erasure-requests/{id}/reject` (Role: `admin`)

---

## 3. LỘ TRÌNH THỰC HIỆN (5 BƯỚC)

1. **Bước 1**: Tạo nhánh Git `feature/SCRUM-92-xoa-du-lieu-ca-nhan`, khai báo model `DataErasureRequest`, export trong `models/__init__.py` và tạo migration Alembic hợp nhất heads.
2. **Bước 2**: Xây dựng Schemas Pydantic (`schemas/data_erasure.py`) và Service nghiệp vụ ẩn danh hóa dữ liệu (`services/privacy_service.py`).
3. **Bước 3**: Xây dựng Router REST API (`routers/privacy.py`) với đầy đủ phân quyền và đăng ký vào `main.py`.
4. **Bước 4**: Viết bộ Unit Test chuyên biệt (`backend/tests/unit/test_data_erasure_scrum92.py`) bao phủ 100% các ca AC, edge case (ví còn tiền, phiên đang sạc, chống trùng, ẩn danh hóa không thể đảo ngược, phân quyền).
5. **Bước 5**: Chạy toàn bộ test suite (gồm cả test migrations), xuất bản Hợp đồng API tại `ketqua/SCRUM-92_hop_dong_api.md`, cập nhật `ketqua/nhat_ky.md` và hoàn tất commit.
