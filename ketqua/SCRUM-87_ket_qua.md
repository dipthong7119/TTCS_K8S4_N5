# SCRUM-87 — Chốt và khóa kỳ đối soát

## Thay đổi

- Thêm `reconciliation_period_locks` và Alembic migration `h20261021_scrum87_reconciliation_period_locks` để lưu snapshot, trạm, kỳ, người chốt và thời điểm chốt.
- Thêm `POST /api/reconciliation/financial/lock`; lần chốt lặp trả lại snapshot đã lưu, không ghi thêm audit.
- `GET /api/reconciliation/financial` trả snapshot đã chốt khi truy vấn đúng trạm và kỳ.
- `admin`, `accountant` và chủ trạm có thể xem; dữ liệu của chủ trạm chỉ truy vấn các trạm họ sở hữu. Người chốt bị giới hạn ở trạm mình.
- Không chốt ngày hiện tại/tương lai, kỳ còn phiên đang mở hoặc bất thường, hoặc báo cáo còn sai lệch cần xem xét.
- Chặn StartTransaction/StopTransaction đến muộn và bước tạo hóa đơn/trừ ví nếu ngày kết thúc thuộc kỳ đã khóa; khóa hàng trạm trong giao dịch để đồng bộ thao tác ghi với thao tác chốt.
- Trang hiển thị trạng thái kỳ, yêu cầu xác nhận trước khi chốt, và khóa nút sau khi chốt.

## Giả định nghiệp vụ

- Khóa theo từng cặp `station_id + from_date + to_date`; ngày của phiên là ngày kết thúc tại múi giờ trạm.
- Kỳ chỉ chốt sau khi ngày kết thúc đã qua. Không có API mở lại kỳ trong phạm vi yêu cầu này.
- Phiên đang mở hoặc cần xem xét liên quan đến kỳ khiến thao tác chốt bị từ chối; không tự giải quyết hay bỏ qua bất thường.
- Snapshot chứa toàn bộ báo cáo chưa lọc loại sai lệch; bộ lọc khi đọc chỉ chọn dòng/tổng từ snapshot đó.

## Kiểm tra

- `pytest tests/unit/test_financial_reconciliation.py --tb=short -q`: 7 passed.
- Đối soát cùng test StartTransaction, StopTransaction, billing tariff và SCRUM-210: 46 passed.
- `node --test --test-name-pattern="SCRUM-85|SCRUM-87" tests/frontend_behavior.cjs`: 4 passed.
- Ruff: đạt.
- `alembic upgrade head` trên SQLite tạm: thành công, head `h20261021_scrum87_reconciliation_period_locks`.
