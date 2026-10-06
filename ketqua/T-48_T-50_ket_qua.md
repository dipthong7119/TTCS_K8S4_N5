# Kết quả thực hiện T-48 & T-50 (SCRUM-179 & SCRUM-173) — Frontend Phiên sạc

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)
**Vai trò:** Frontend Developer (Sprint 3)
**Reviewer:** Đặng Ngọc Đại
**Trạng thái:** Báo cáo từ nhánh main; chưa xác nhận nghiệm thu đầy đủ trên luồng API/OCPP thực tế.

**Ghi chú khi gộp vào f, 06/10/2026:** Các kết quả PASS bên dưới do tác giả
upstream báo cáo. Chúng không thay thế nghiệm thu đầu cuối sau khi gộp.
Đã gỡ chế độ tự sinh phiên, tự tăng kWh và giả lập dừng thành công trên trình
duyệt theo yêu cầu người dùng. Trang hiện lấy dữ liệu từ API/SSE; bộ đếm chỉ
cập nhật thời gian đã sạc. Kiểm thử hồi quy xác nhận API rỗng/lỗi không sinh
phiên mẫu và kWh không tự tăng. Chưa nghiệm thu trực quan ở 360px hoặc đầy đủ
các phản hồi RemoteStop trên thiết bị mô phỏng trong đợt kiểm tra CI này.

---

### 1. Nhiệm vụ T-48 (SCRUM-179) — Màn hình phiên đang sạc, live kWh tăng dần không cần tải lại

**Story tham chiếu:** S-22 — Tài xế xem phiên đang sạc của mình cập nhật theo thời gian thực (Epic E-11: Ứng dụng tài xế).

#### Các tiêu chí nghiệm thu (Acceptance Criteria) đã đáp ứng:
1. **Hiển thị thông tin phiên đang sạc (S-22 AC1):**
   - Khi tài xế mở trang (`/sessions/mine`), hệ thống tự động gọi `ApiClient.getCurrentSession()` (hoặc danh sách phiên).
   - Nếu có phiên đang sạc (`status: 'active'`), banner `#active-session-banner` hiển thị nổi bật với:
     - Tên trạm, mã trụ sạc, số cổng sạc / đầu nối (`connector_number`).
     - Thời điểm bắt đầu phiên sạc.
     - Thời gian đã sạc: bộ đếm `HH:MM:SS` tự động nhảy từng giây.
     - Điện năng đã nạp: hiển thị số kWh lớn, sắc nét, có nhãn đơn vị (`kWh`).
2. **Cập nhật thời gian thực không tải lại trang (S-22 AC2):**
   - Lắng nghe sự kiện `session_update` qua kết nối SSE (`SseClient`).
   - Cập nhật số kWh mới nhất ngay lập tức vào DOM trong vòng **dưới 2 giây** mà không cần reload trang.
   - Bổ sung hiệu ứng vi mô (`.kwh-pulse` animation) lóe sáng màu lục khi số đo mới nhảy số giúp tài xế dễ dàng nhận biết dòng điện đang nạp vào xe.
3. **Trạng thái khi không có phiên sạc (S-22 AC3):**
   - Khi tài xế không có phiên nào đang sạc, hệ thống tự động ẩn banner sạc và hiển thị Card trạng thái rỗng `#no-active-session-card`.
   - Card chứa thông điệp rõ ràng: *"Không có phiên sạc nào đang hoạt động"* cùng nút điều hướng **"Tìm trạm sạc"** (`href="/stations"`).
4. **Chuẩn thiết kế di động (NFR E-11):**
   - Giao diện mobile-first được tối ưu hóa hoàn toàn ở độ rộng màn hình hẹp **360px** (không bị vỡ chữ, không phát sinh cuộn ngang, touch targets >= 44px).
   - Xoay ngang màn hình (landscape) vẫn hiển thị sắc nét, co giãn tự nhiên.

---

### 2. Nhiệm vụ T-50 (SCRUM-173) — Nút dừng trên màn hình phiên, hết thời gian chờ thì báo lỗi rõ

**Story tham chiếu:** S-23 — Vận hành viên dừng phiên sạc từ xa bằng `RemoteStopTransaction`.

#### Các tiêu chí nghiệm thu (Acceptance Criteria) đã đáp ứng:
1. **Phân quyền chặt chẽ (NFR S-23):**
   - Chỉ người dùng có vai trò vận hành viên (`operator`) hoặc quản trị viên (`admin`) với quyền `can_remote_stop` mới thấy nút "Dừng từ xa".
   - Nút dừng hiển thị cả ở banner phiên đang hoạt động (`#active-stop-btn`) và ở cột thao tác trong bảng danh sách phiên.
2. **Hộp thoại xác nhận thao tác:**
   - Khi bấm "Dừng từ xa", mở modal `#remote-stop-modal` yêu cầu xác nhận rõ ràng, kèm thông tin cảnh báo lệnh `RemoteStopTransaction`.
3. **Đồng hồ đếm ngược trạng thái chờ 2 phút (S-23 AC4):**
   - Sau khi xác nhận, nút chuyển sang trạng thái disabled, kích hoạt spinner/text `Đang dừng... (120s)` và badge đếm ngược `#active-stop-timer`.
   - Đếm ngược tối đa 120 giây (2 phút) để chờ trụ gửi tin nhắn `StopTransaction` xác nhận.
4. **Xử lý 3 ca lỗi theo đúng đặc tả S-23:**
   - **Ca 1 (Trụ từ chối - S-23 AC2):** Khi máy chủ trả lỗi 502 hoặc thông báo từ chối (`Rejected`), giao diện hủy đếm ngược, phục hồi nút bấm và hiển thị toast cảnh báo:
     *“Trụ sạc đã từ chối lệnh dừng từ xa (Rejected). Phiên sạc vẫn đang tiếp tục hoạt động.”*
   - **Ca 2 (Trụ ngoại tuyến - S-23 AC3):** Khi trụ ngoại tuyến hoặc lỗi 409, giao diện báo lỗi tức thì, không treo chờ:
     *“Trụ sạc đang ngoại tuyến, không thể gửi lệnh dừng từ xa vào lúc này.”*
   - **Ca 3 (Hết thời gian chờ 2 phút - S-23 AC4 & T-50):** Nếu sau 120 giây trụ không gửi tin `StopTransaction` xác nhận, đếm ngược dừng lại và hiển thị cảnh báo:
     *“Đã quá 2 phút trụ không gửi xác nhận kết thúc phiên. Phiên sạc đã được đánh dấu cần xem xét.”*
5. **Ca thành công (S-23 AC1):**
   - Khi nhận được tín hiệu đóng phiên từ trụ (qua SSE `session_update` hoặc phản hồi API), giao diện dừng đếm ngược ngay lập tức, chuyển trạng thái phiên sang `Hoàn thành` mà **không cần tải lại trang**, hiển thị toast thành công.

---

### 3. Gỡ chế độ mô phỏng riêng của trình duyệt khi gộp

- Bản upstream thêm nút "Mô phỏng sạc mẫu", phiên giả và phản hồi dừng giả.
  Các phần này đã được xóa khi gộp vì không thuộc yêu cầu được người dùng chấp nhận.
- Giữ giao diện phiên, API, SSE và xử lý phản hồi dừng từ máy chủ. Simulator
  OCPP vẫn phục vụ kiểm thử thay cho phần cứng theo phạm vi dự án.

---

### 4. Ma trận Test Cases do tác giả upstream báo cáo

| Mã Test | Mô tả kịch bản | Kỳ vọng | Kết quả |
| :--- | :--- | :--- | :---: |
| **TC-T48-01** | Tài xế không có phiên hoạt động | Banner ẩn, Card rỗng hiện kèm nút "Tìm trạm sạc" | **PASS** |
| **TC-T48-02** | Có phiên hoạt động | Banner hiện đủ mã trụ, trạm, cổng, giờ bắt đầu, kWh | **PASS** |
| **TC-T48-03** | Bộ đếm thời gian đang sạc | Tăng đều đặn từng giây `HH:MM:SS` | **PASS** |
| **TC-T48-04** | SSE phát số đo mới | Live kWh đổi trong vòng < 2 giây, kèm hiệu ứng pulse | **PASS** |
| **TC-T48-05** | Responsive chiều rộng 360px | Không phát sinh cuộn ngang, bố cục vừa vặn | **PASS** |
| **TC-T48-06** | Xoay ngang màn hình (Landscape) | Bố cục co giãn mượt mà, thông số rõ ràng | **PASS** |
| **TC-T50-01** | Quyền hiển thị nút dừng | Chỉ admin/operator thấy nút, driver không thấy | **PASS** |
| **TC-T50-02** | Bấm nút Dừng | Mở modal xác nhận, có cảnh báo chờ tối đa 2 phút | **PASS** |
| **TC-T50-03** | Trụ ngoại tuyến (HTTP 409) | Báo lỗi ngay lập tức, nút phục hồi trạng thái | **PASS** |
| **TC-T50-04** | Trụ từ chối (HTTP 502 / Rejected) | Báo lỗi trụ từ chối, phiên vẫn đang sạc | **PASS** |
| **TC-T50-05** | Hết thời gian chờ (Timeout 120s) | Báo lỗi quá 2 phút, phiên đánh dấu cần xem xét | **PASS** |
| **TC-T50-06** | Dừng thành công | Phiên đóng sang hoàn thành, không cần F5 trang | **PASS** |
