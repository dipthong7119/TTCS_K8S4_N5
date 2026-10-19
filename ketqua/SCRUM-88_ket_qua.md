# SCRUM-88 — Xuất CSV báo cáo đối soát

## Thay đổi

- Thêm `GET /api/stations/{station_id}/revenue.csv` cho báo cáo doanh thu trạm (SCRUM-84), theo khoảng ngày đã chọn và quyền xem doanh thu của trạm.
- Thêm `GET /api/subscriptions/revenue-share.csv` cho báo cáo chia doanh thu (SCRUM-86), theo khoảng ngày và đối tác đã chọn.
- Thêm `GET /api/reconciliation/financial.csv` cho đối soát tài chính (SCRUM-85/87), giữ nguyên bộ lọc ngày, trạm, trụ, loại sai lệch và đọc snapshot nếu kỳ đã khóa.
- Các endpoint gọi lại cùng hàm báo cáo hiện có; CSV có dòng tổng và các dòng chi tiết. Bộ mã dùng BOM UTF-8, `csv.writer` để escape dấu phẩy/dấu ngoặc kép/xuống dòng, xuống dòng CRLF, ngày ISO, kWh ba chữ số thập phân và VND dạng số nguyên.
- Thêm nút tải ở ba trang. Nút gửi đúng bộ lọc đang chọn, hiển thị trạng thái tải/thành công/lỗi và dùng `ApiClient` để tải tệp.

## Giả định nghiệp vụ

- Dòng `TOTAL` đứng đầu tệp để đối chiếu với KPI/tổng chân bảng; các dòng tiếp theo là chi tiết theo trụ, hợp đồng hoặc phiên.
- Giá trị VND trong CSV là số nguyên không phân tách hàng nghìn; kWh cố định ba chữ số thập phân. Trường rỗng được để trống.
- Báo cáo đối soát đã khóa xuất từ snapshot đã lưu; lọc sai lệch/trụ vẫn được áp dụng như khi xem trên trang.
- Tên tệp chứa loại báo cáo và khoảng ngày; với báo cáo trạm/đối tác có thêm mã định danh khi phù hợp.

## Kiểm tra

- `pytest tests/unit/test_csv_reports.py tests/unit/test_station_revenue.py tests/unit/test_revenue_sharing.py tests/unit/test_financial_reconciliation.py -q`: 17 passed.
- `node --test --test-name-pattern=SCRUM-88 tests/frontend_behavior.cjs`: 4 passed.
- Ruff trên các router, helper và test liên quan: đạt.
- Không có thay đổi schema nên không cần migration.
