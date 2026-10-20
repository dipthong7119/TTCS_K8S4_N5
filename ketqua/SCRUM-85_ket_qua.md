# SCRUM-85 — Đối soát điện năng và tiền thu

## Thay đổi

- Thêm `GET /api/reconciliation/financial` cho `admin` và `accountant`.
- Báo cáo dùng phiên đã hoàn tất, giá biểu lịch sử/giá gói, hóa đơn bất biến, số đo công-tơ và bút toán ví theo tham chiếu phiên.
- Kỳ lọc tính theo ngày kết thúc phiên ở múi giờ trạm; hỗ trợ lọc trạm, trụ và loại sai lệch.
- Màn hình bỏ JavaScript dữ liệu mẫu, gọi ApiClient và hiển thị kWh, tiền theo giá, hóa đơn, tiền thực thu, chênh lệch cùng danh sách phiên cần rà soát.
- Thêm trường hợp thiếu giá, thiếu hóa đơn, thiếu bút toán, lệch hóa đơn/giá và lệch bút toán/hóa đơn.

## Giả định nghiệp vụ

- `payment_transactions` trong codebase là giao dịch nạp ví; nó không tham chiếu phiên sạc. Tiền thực thu cho phiên vì vậy lấy từ sổ cái `wallet_ledger` với `entry_type=session_charge`, `reference_type=session`, `reference_id=session_id`.
- Phiên thuộc kỳ theo ngày kết thúc (`ended_at`) ở múi giờ trạm.
- Tiền phải thu tính lại bằng cùng bộ tính giá và dữ liệu biểu giá/đăng ký có hiệu lực khi phát sinh phiên; tổng lệch là tổng trị tuyệt đối từng phiên để các khoản trái dấu không triệt tiêu.
- Chỉ báo cáo phiên hoàn tất, không phải dữ liệu demo. Kỳ không có dữ liệu trả về tổng bằng 0 và danh sách rỗng.

## Kiểm tra

- `pytest tests/unit/test_financial_reconciliation.py --tb=short -q`: 3 passed.
- `node --test --test-name-pattern="SCRUM-85" tests/frontend_behavior.cjs`: 3 passed.
- Ruff trên router, service, tính giá, test: đạt.
- Bộ dữ liệu kiểm tra tính tay gồm phiên lệch hóa đơn/tiền thu, phiên thiếu hóa đơn và phiên thiếu bút toán; tổng kWh, tiền theo biểu giá, tiền hóa đơn, tiền thu và chênh lệch đều được khẳng định trong test.
