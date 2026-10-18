# KẾ HOẠCH LÀM VIỆC CHI TIẾT: SCRUM-91 (SPRINT 8) — HOÀNG VĂN ĐỨC

* **Họ và tên**: Hoàng Văn Đức
* **Vai trò**: Backend Developer
* **Epic phụ trách**: Giám sát vận hành (*Operational Monitoring*)
* **Nhiệm vụ trọng tâm**: **SCRUM-91** — *Nhật ký thao tác trên giao dịch ví truy được ai làm gì* (3 SP)
* **Story gốc trong đặc tả**: [S-56](file:///d:/TTCS_K8S4_N5/prompts/02_DAC_TA_DU_AN.md#L1195)
* **Nhánh Git làm việc**: `feature/SCRUM-91-nhat-ky-giao-dich-vi`
* **Người phối hợp Frontend (subtask FE)**: Phạm Văn Tuấn (Màn hình nhật ký & tra cứu giao dịch ví)
* **Người Reviewer / QA chéo**: Ngô Quang Tùng (Quang Tùng kiểm thử & review Đức; Đức review Tạ Như Vinh)
* **Căn cứ kế hoạch**:
  - Phân công Sprint 678: [`prompts/phan-cong-sprint-678.md`](file:///d:/TTCS_K8S4_N5/prompts/phan-cong-sprint-678.md)
  - Quy tắc Agent: [`prompts/00_QUY_TAC_AGENT.md`](file:///d:/TTCS_K8S4_N5/prompts/00_QUY_TAC_AGENT.md)
  - Codebase Map: [`prompts/01_CODEBASE_MAP.md`](file:///d:/TTCS_K8S4_N5/prompts/01_CODEBASE_MAP.md)
  - Đặc tả yêu cầu: Story S-56 tại [`prompts/02_DAC_TA_DU_AN.md`](file:///d:/TTCS_K8S4_N5/prompts/02_DAC_TA_DU_AN.md#L1195)

---

## 1. MỤC TIÊU VÀ TIÊU CHUẨN NGHIỆM THU (ACCEPTANCE CRITERIA)

### 1.1. Story S-56 (Sprint 8, 3 SP)
* **User Story**: Là quản trị hệ thống tôi muốn truy được ai đã nạp tay, ai đã điều chỉnh ví nào lúc nào để điều tra khi có khiếu nại về số dư.
* **Tiêu chuẩn nghiệm thu (Acceptance Criteria - Given/When/Then)**:
  1. **AC1 — Nhật ký nạp tiền thủ công**: Khi Admin nạp tay cho tài xế (`manual_topup`), hệ thống ghi lại một dòng vào `audit_logs` gồm: người thực hiện (`actor_id`, `actor_email`, `actor_name`), tài xế được nạp (`target_user_id`, `driver_name`, `driver_email`), số tiền (`amount_vnd`), lý do/ghi chú (`reason`), mã phiếu thu (`receipt_code`).
  2. **AC2 — Nhật ký điều chỉnh số dư ví**: Khi Admin thực hiện điều chỉnh ví (bồi hoàn, xử lý sự cố, hiệu chỉnh sai lệch), hệ thống ghi nhận vào `audit_logs` hành động `wallet.adjust` với đầy đủ người thực hiện, tài xế, số tiền chênh lệch, và bắt buộc phải có lý do điều chỉnh (`reason`).
  3. **AC3 — Nhật ký khóa / mở khóa ví**: Khi Admin thao tác khóa hoặc mở khóa ví tài xế, hệ thống ghi nhận vào `audit_logs` hành động `wallet.lock` / `wallet.unlock` kèm người thực hiện, tài xế và lý do.
  4. **AC4 — Tra cứu nhật ký lọc theo tài xế**: API `GET /api/audit` bổ sung tham số lọc `driver_id` (hoặc tên/email tài xế `driver`) và lọc theo `action`. Cho phép quản trị viên xem toàn bộ lịch sử can thiệp vào ví của một tài xế cụ thể trong khoảng thời gian.
  5. **AC5 — Tính toàn vẹn & Bất biến (Immutability)**: Bảng `audit_logs` tiếp tục tuân thủ nguyên tắc chỉ ghi thêm (append-only), mọi thao tác sửa hoặc xóa qua API đều bị từ chối bằng HTTP 405.

---

## 2. THIẾT KẾ KỸ THUẬT VÀ RÀNG BUỘC KIẾN TRÚC

### 2.1. CSDL & Migration Alembic
* Bổ sung cột `target_user_id` vào bảng `audit_logs`:
  - `target_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)`
  - Tạo Index kết hợp: `ix_audit_logs_target_created` trên `(target_user_id, created_at)`.
  - Tạo migration Alembic `h20261013_audit_target_user.py` kế thừa head hiện tại.

### 2.2. Tầng Service Nghiệp vụ
* Cập nhật `backend/app/services/audit.py`:
  - Mở rộng hàm `ghi_nhat_ky` hỗ trợ `target_user_id: int | None = None`.
* Cập nhật `backend/app/services/wallet.py`:
  - Chuẩn hóa ghi log nạp tay `manual_topup`: bổ sung đầy đủ `target_user_id`, `actor_email`, `actor_name`, `driver_email`, `driver_name`, `reason`.
  - Xây dựng hàm `adjust_wallet_balance(db, admin_user, driver_id, amount_vnd, reason)`: điều chỉnh số dư hợp lệ, ghi sổ cái và ghi nhật ký kiểm toán `wallet.adjust`.
  - Xây dựng hàm `set_driver_wallet_lock(db, admin_user, driver_id, lock: bool, reason)`: khóa hoặc mở khóa ví, ghi nhật ký `wallet.lock` / `wallet.unlock`.

### 2.3. Tầng Router REST API
* Cập nhật `backend/app/routers/audit.py`:
  - Thêm Query params: `driver_id: int | None`, `driver: str | None`, `action: str | None`.
  - Trả về thông tin chi tiết tài xế trong từng dòng nhật ký.
* Cập nhật `backend/app/routers/wallet.py`:
  - Thêm endpoint `POST /api/admin/wallets/{driver_id}/adjust` (quyền `admin`).
  - Thêm endpoint `POST /api/admin/wallets/{driver_id}/lock` và `POST /api/admin/wallets/{driver_id}/unlock` (quyền `admin`).

---

## 3. LỘ TRÌNH THỰC HIỆN (5 BƯỚC)

1. **Bước 1**: Tạo nhánh Git `feature/SCRUM-91-nhat-ky-giao-dich-vi`, mở rộng model `AuditLog` và tạo migration Alembic.
2. **Bước 2**: Hoàn thiện tầng Service nghiệp vụ ví & kiểm toán thao tác (`wallet.py`, `audit.py`).
3. **Bước 3**: Cập nhật Router API (`audit.py`, `wallet.py`) với bộ lọc theo tài xế và các endpoints quản trị ví.
4. **Bước 4**: Viết bộ Unit Test chuyên biệt (`backend/tests/unit/test_wallet_audit_scrum91.py`) đạt 100% pass.
5. **Bước 5**: Xuất bản Hợp đồng API `ketqua/SCRUM-91_hop_dong_api.md`, cập nhật `ketqua/nhat_ky.md` và gộp/push nhánh.
