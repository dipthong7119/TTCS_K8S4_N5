# Kết quả thực hiện SCRUM-74 — Màn hình xem số dư và lịch sử giao dịch ví (Tài xế)

**Người thực hiện:** Phạm Văn Tuấn (Frontend Developer)  
**Vai trò:** Frontend Developer (Sprint 3)  
**Epic:** Ví và thanh toán  
**Story cha:** SCRUM-74 (Tài xế xem số dư và lịch sử giao dịch ví)  
**Người phối hợp Backend:** Nguyễn Lâm Tùng / Hoàng Văn Đức  
**Reviewer:** Vy Hoàng Tú  
**Trạng thái:** Hoàn tất 100% triển khai Frontend & Tích hợp API  

---

### 1. Mục tiêu và Tiêu chí nghiệm thu (Acceptance Criteria)

- **Mục tiêu:** Cung cấp cho tài xế màn hình trực quan để theo dõi số dư ví thời gian thực, kiểm tra điều kiện kích hoạt sạc (ngưỡng tối thiểu 50.000 ₫), tra cứu chi tiết toàn bộ các bút toán sổ cái (nạp tiền, trừ tiền phiên sạc, phí thuê bao, hoàn tiền) và xuất sao kê giao dịch phục vụ đối soát chi phí.
- **Tiêu chí nghiệm thu:**
  1. **Hiển thị số dư thời gian thực:**
     - Hiển thị số dư khả dụng, mã tài khoản ví (`account_id`), tổng tiền nạp và tổng tiền chi tiêu qua `GET /api/wallet`.
     - Chỉ báo trực quan trạng thái số dư tối thiểu (đủ điều kiện sạc khi ≥ 50.000 ₫ hoặc cảnh báo khi < 50.000 ₫ theo SCRUM-199/72).
  2. **Tra cứu lịch sử giao dịch sổ cái (Append-only Ledger):**
     - Hiển thị danh sách bút toán sổ cái đầy đủ: Thời gian, loại giao dịch, mô tả, số tiền (màu xanh `+` cho credit, màu đỏ `-` cho debit), số dư sau giao dịch.
     - Phân loại bằng badge rõ ràng: `Nạp Sandbox`, `Nạp thủ công`, `Nạp demo`, `Phiên sạc`, `Phí gói tháng`, `Hoàn tiền`.
     - Liên kết trực tiếp: Khi bút toán là chi phí phiên sạc (`session_id`), hiển thị đường dẫn click xem chi tiết phiên sạc.
  3. **Bộ lọc đa chiều & Tìm kiếm thời gian thực:**
     - Lọc theo khoảng thời gian: 7 ngày, 30 ngày, 90 ngày, 180 ngày, hoặc Tất cả.
     - Lọc theo dòng tiền: Tất cả loại, Tiền vào (+), Tiền ra (-), Phiên sạc, Nạp Sandbox, Nạp thủ công.
     - Ô tìm kiếm từ khóa thời gian thực: Tìm nhanh theo mã phiên sạc, mã đối soát, hoặc nội dung diễn giải.
     - Dòng tóm tắt thống kê: Hiển thị số lượng giao dịch tìm thấy kèm tổng tiền vào (+) và tổng tiền ra (-) trong kỳ lọc.
  4. **Modal Chi tiết bút toán giao dịch (Ledger Entry Details):**
     - Cho phép tài xế bấm vào từng dòng giao dịch để mở cửa sổ chi tiết: Mã bút toán `#LEDGER-...`, thời gian chính xác, số tiền, số dư sau giao dịch, mã tham chiếu/phiên sạc liên quan, toàn văn diễn giải.
  5. **Xuất sao kê giao dịch (Export Statement):**
     - Nút "Xuất CSV" xuất file sao kê có gắn mã BOM UTF-8 (chuẩn tiếng Việt không lỗi font trong Excel) tải xuống file `sao_ke_vi_[account_id]_[date].csv`.

---

### 2. Các tệp triển khai và thay đổi

| Thành phần | Đường dẫn file | Mô tả chi tiết |
|---|---|---|
| **Giao diện Ví** | `frontend/templates/wallet/wallet.html` | Cập nhật thanh công cụ lọc sổ cái, bảng lịch sử giao dịch 6 cột, footer tóm tắt dòng tiền, modal chi tiết bút toán `#ledger-detail-modal`. |
| **Styles (CSS)** | `frontend/static/css/pages/wallet.css` | Bổ sung class `.ledger-toolbar`, `.ledger-detail-hero`, `.btn-ledger-detail`, `.clickable-row`, responsive cho thiết bị di động. |
| **Logic (JavaScript)** | `frontend/static/js/pages/wallet.js` | Logic tải dữ liệu sổ cái `ApiClient.listLedger`, lọc đa chiều, tìm kiếm tức thì, tính tổng dòng tiền, render modal chi tiết và xuất file CSV. |
| **Báo cáo kết quả** | `ketqua/SCRUM-74_ket_qua.md` | Tài liệu báo cáo kết quả và nghiệm thu các tiêu chí SCRUM-74. |
| **Nhật ký dự án** | `ketqua/nhat_ky.md` | Cập nhật tiến độ hoàn thành SCRUM-74. |

---

### 3. Ma trận kiểm thử nghiệm thu (Test Cases)

| Mã Test | Kịch bản kiểm thử | Kết quả kỳ vọng | Trạng thái |
|:---:|---|---|:---:|
| **TC-74-01** | Truy cập trang `/wallet` bằng tài khoản driver | Hiển thị chính xác số dư ví, mã tài khoản `W-0000xx`, tổng nạp và tổng chi | **PASS** |
| **TC-74-02** | Hiển thị bảng lịch sử sổ cái qua `GET /api/wallet/ledger` | Bảng hiển thị đầy đủ các cột thời gian, loại bút toán, diễn giải, số tiền, số dư sau | **PASS** |
| **TC-74-03** | Lọc theo thời gian (7 ngày, 30 ngày, 90 ngày, Tất cả) | Gửi tham số `days` lên backend và cập nhật đúng danh sách giao dịch tương ứng | **PASS** |
| **TC-74-04** | Lọc theo loại dòng tiền (Tiền vào vs Tiền ra) | Lọc chính xác các giao dịch cộng tiền (credit) hoặc trừ tiền (debit) | **PASS** |
| **TC-74-05** | Tìm kiếm từ khóa theo mã phiên / mô tả | Danh sách lọc tức thì theo từ khóa nhập vào, hiển thị số kết quả khớp | **PASS** |
| **TC-74-06** | Nhấp vào một dòng giao dịch hoặc nút "Chi tiết" | Mở modal hiển thị toàn bộ thông tin chi tiết của bút toán sổ cái | **PASS** |
| **TC-74-07** | Nhấp vào nút "Xuất CSV" | Tải xuống file `sao_ke_vi_...csv` có BOM UTF-8, mở tiếng Việt hoàn hảo trên Excel | **PASS** |
| **TC-74-08** | Hiển thị link phiên sạc cho bút toán `session_charge` | Nhấp link phiên sạc điều hướng đến trang quản lý phiên sạc của tài xế | **PASS** |

---

### 4. Kết luận & Chuyển giao

- Nhiệm vụ **SCRUM-74 (2 SP chung)** đã hoàn thành 100%, đáp ứng trọn vẹn mọi tiêu chí nghiệm thu cho phân hệ Ví tài xế.
- Sẵn sàng bàn giao cho Reviewer (**Vy Hoàng Tú**) review code.
