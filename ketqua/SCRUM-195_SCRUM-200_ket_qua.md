# Kết quả thực hiện SCRUM-195 & SCRUM-200 — Màn hình/Luồng nạp tiền ví Sandbox & Theo dõi trạng thái giao dịch

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)  
**Vai trò:** Frontend Developer (Sprint 3)  
**Epic:** Ví và thanh toán  
**Story cha:** SCRUM-69 (Tài xế nạp tiền vào ví qua cổng thanh toán sandbox)  
**Nhiệm vụ trực tiếp:**
- **SCRUM-195:** Thêm màn hình/luồng nạp tiền vào ví cho tài xế (FE)
- **SCRUM-200:** Hiển thị số dư ví và trạng thái giao dịch nạp tiền (FE)
**Người phối hợp Backend:** Hoàng Văn Đức (SCRUM-196, 197, 198, 199, 201)  
**Reviewer:** Vy Hoàng Tú  
**Trạng thái:** Hoàn tất 100% triển khai Frontend & Tích hợp API  

---

### 1. Mục tiêu và Tiêu chí nghiệm thu (Acceptance Criteria)

- **Mục tiêu:**
  - Cung cấp luồng nạp tiền trực quan, tiện lợi và an toàn cho tài xế nạp tiền vào ví thông qua Cổng thanh toán Sandbox (SCRUM-195).
  - Cung cấp giao diện hiển thị số dư ví thời gian thực, cảnh báo số dư tối thiểu trước khi sạc, và theo dõi trực quan trạng thái từng đơn nạp tiền (Pending / Success / Failed) cùng lịch sử sổ cái biến động số dư (SCRUM-200).
- **Tiêu chí nghiệm thu:**
  1. **Nạp tiền ví Sandbox (SCRUM-195):**
     - Nút "Nạp tiền vào ví" và "Nạp tiền Sandbox" nổi bật trên thẻ số dư và tiêu đề trang `/wallet`.
     - Modal nạp tiền hỗ trợ các mốc tiền nạp nhanh (50.000 ₫, 100.000 ₫, 200.000 ₫, 500.000 ₫, 1.000.000 ₫, 2.000.000 ₫) và ô nhập tùy biến với live preview định dạng tiền tệ.
     - Ràng buộc hợp lệ: Hạn mức từ 10.000 ₫ đến 10.000.000 ₫.
     - Khởi tạo đơn nạp qua `POST /api/wallet/topups/sandbox`, hiển thị chi tiết mã đơn `order_code`, số tiền và trạng thái `pending`.
     - Cung cấp 2 lựa chọn xử lý:
       - Mở trang Cổng thanh toán Sandbox chi tiết (`/wallet/sandbox-checkout?order_code=...`).
       - Xác nhận thanh toán nhanh giả lập ngay trên modal qua `POST /api/wallet/topups/sandbox/simulate-pay`.
  2. **Theo dõi số dư và trạng thái giao dịch (SCRUM-200):**
     - Hiển thị số dư hiện tại, tổng tiền nạp, tổng tiền chi từ `GET /api/wallet`.
     - Tích hợp kiểm tra số dư tối thiểu qua `GET /api/wallet/check-balance?min_amount_vnd=50000`, cảnh báo nếu số dư < 50.000 ₫ để tài xế chủ động nạp trước khi cắm sạc (SCRUM-199/72).
     - Điều hướng tab phân chia rõ ràng:
       - **Tab 1: Đơn nạp Sandbox:** Hiển thị chi tiết từng đơn nạp, mã đơn, số tiền, badge trạng thái (Chờ thanh toán `status-badge--pending`, Thành công `status-badge--success`, Thất bại `status-badge--failed`). Hỗ trợ nút "Thanh toán ngay" cho các đơn còn `pending`.
       - **Tab 2: Sổ cái giao dịch:** Xem lịch sử biến động số dư chi tiết (`sandbox_topup`, `manual_topup`, `session_charge`, `subscription_charge`, `refund`).
     - Phân trang đầy đủ cho cả danh sách đơn nạp và sổ cái.
  3. **Màn hình Cổng thanh toán Sandbox (`/wallet/sandbox-checkout`):**
     - Màn hình giả lập cổng thanh toán trực quan với thông tin đơn hàng, quét mã QR demo và thẻ ATM.
     - Nút "Xác nhận thanh toán thành công" và "Mô phỏng thanh toán thất bại" phục vụ kiểm thử end-to-end.
     - Tự động chuyển hướng về trang ví với thông báo toast khi thanh toán thành công.

---

### 2. Chi tiết các tệp thay đổi và triển khai

| Thành phần | Đường dẫn file | Mô tả công việc |
|---|---|---|
| **API Client** | `frontend/static/js/api_client.js` | Bổ sung 4 phương thức API trung tâm: `createSandboxTopup()`, `simulateSandboxPay()`, `listTopupHistory()`, `checkWalletBalance()`. |
| **Giao diện Ví** | `frontend/templates/wallet/wallet.html` | Bổ sung nút Nạp tiền, cảnh báo số dư tối thiểu, cấu trúc tab Đơn nạp vs Sổ cái, modal nạp tiền 2 bước (SCRUM-195/200). |
| **Styles (CSS)** | `frontend/static/css/pages/wallet.css` | Thiết kế giao diện thẻ số dư, preset buttons, modal backdrop/dialog, badges trạng thái đơn nạp, responsive layout và sandbox checkout. |
| **Logic (JS)** | `frontend/static/js/pages/wallet.js` | Logic mở/đóng modal, validate hạn mức, gọi API tạo đơn nạp, mô phỏng thanh toán, render bảng đơn nạp sandbox, phân trang và tab switching. |
| **Cổng Sandbox** | `frontend/templates/wallet/sandbox_checkout.html` | Trang mô phỏng cổng thanh toán độc lập phục vụ kiểm thử kịch bản tài xế quét QR/thẻ. |
| **Routing** | `backend/app/routers/pages.py` | Đăng ký route giao diện `GET /wallet/sandbox-checkout` dành riêng cho role `driver`. |

---

### 3. Ma trận kiểm thử nghiệm thu (Test Cases)

| Mã Test | Mô tả kịch bản kiểm thử | Kết quả kỳ vọng | Trạng thái |
|---|---|---|:---:|
| **TC-195-01** | Bấm nút "Nạp tiền vào ví" từ giao diện tài xế | Mở modal nạp tiền Sandbox với các nút chọn nhanh 50k, 100k, 200k, 500k, 1M, 2M | **PASS** |
| **TC-195-02** | Nhập số tiền < 10.000 ₫ hoặc > 10.000.000 ₫ | Hiển thị cảnh báo lỗi vi phạm hạn mức, không cho gửi yêu cầu | **PASS** |
| **TC-195-03** | Khởi tạo đơn nạp 100.000 ₫ | Gửi `POST /api/wallet/topups/sandbox` thành công, chuyển sang Bước 2 hiển thị mã đơn | **PASS** |
| **TC-195-04** | Bấm "Xác nhận thanh toán ngay" trên modal | Gọi `simulate-pay`, cập nhật số dư tức thì, reload bảng đơn nạp và đóng modal | **PASS** |
| **TC-195-05** | Truy cập `/wallet/sandbox-checkout?order_code=...` | Hiển thị thông tin đơn, QR code mô phỏng, nút xác nhận thành công / thất bại | **PASS** |
| **TC-200-01** | Hiển thị số dư ví và tổng nạp/tổng chi | Số dư hiển thị chính xác theo tiền tệ VNĐ từ API authoritative | **PASS** |
| **TC-200-02** | Kiểm tra số dư tối thiểu kích hoạt sạc | Nếu số dư < 50.000 ₫ hiển thị cảnh báo màu cam; nếu ≥ 50.000 ₫ hiển thị badge xanh đủ điều kiện | **PASS** |
| **TC-200-03** | Hiển thị danh sách đơn nạp tiền Sandbox | Bảng hiển thị đầy đủ thời gian, mã đơn, số tiền, trạng thái `pending`/`success`/`failed` | **PASS** |
| **TC-200-04** | Xử lý đơn nạp có trạng thái `pending` | Có nút "Thanh toán ngay" để người dùng tiếp tục giao dịch dang dở | **PASS** |
| **TC-200-05** | Chuyển đổi giữa tab Đơn nạp và Sổ cái giao dịch | Dữ liệu chuyển đổi mượt mà, phân trang độc lập | **PASS** |

---

### 4. Kết luận

- **SCRUM-195** và **SCRUM-200** đã hoàn tất 100%, tích hợp hoàn toàn khớp với backend contract của Hoàng Văn Đức tại `ketqua/SCRUM-69_hop_dong_api_vi.md`.
- Sẵn sàng phối hợp cùng Hoàng Văn Đức thực hiện **SCRUM-202** (Test chức năng nạp tiền ví qua sandbox) và bàn giao cho Vy Hoàng Tú review.
