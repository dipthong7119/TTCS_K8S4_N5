# SCRUM-86 — Chia doanh thu theo hợp đồng có phiên bản

## Thay đổi

- Thêm bảng `revenue_share_contracts` và migration `h20261020_scrum86_revenue_share_contracts`.
- Thêm API kế toán/quản trị để xem và thêm hợp đồng tại `/api/subscriptions/revenue-share/contracts`.
- Báo cáo chia doanh thu đọc hợp đồng hiệu lực tại thời điểm phát sinh usage; hợp đồng mới có ngày hiệu lực tương lai và tự đóng hợp đồng trước tại mốc đó.
- Chia tiền nguyên đồng bằng largest remainder; phần của nền tảng là phần còn lại để tổng luôn khớp.
- Cập nhật trang chia doanh thu để nhập, xem lịch sử hợp đồng và hiển thị tỉ lệ đang áp dụng.

## Giả định nghiệp vụ

- Đối tác được xác định theo chủ sở hữu trạm, phù hợp với `SubscriptionUsage.station_owner_id` hiện có.
- Phí chiếm chỗ và doanh thu phiên sạc lẻ không thuộc pool gói thuê bao của SCRUM-86.
- Hợp đồng không được hồi tố: migration lưu chính sách cũ 60/40 từ 1970 cho các chủ trạm hiện hữu; hợp đồng tạo qua API chỉ có hiệu lực trong tương lai. Vì vậy hợp đồng mới không làm tính lại kỳ đã phát sinh.
- Phần chia cho đối tác làm tròn HALF_UP đến đồng trên từng usage; phần nền tảng nhận phần dư nguyên đồng.

## Kiểm tra

- `pytest tests/unit/test_monthly_subscriptions.py tests/unit/test_revenue_sharing.py --tb=short -q`: 8 passed.
- `node --test --test-name-pattern="SCRUM-86|SCRUM-254" tests/frontend_behavior.cjs`: 5 passed.
- Ruff trên service, model, schema, router, migration và test liên quan: đạt.
- `alembic upgrade head` trên SQLite tạm: thành công, head `h20261020_scrum86_revenue_share_contracts`.
