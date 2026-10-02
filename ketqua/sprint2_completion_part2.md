# Sprint 2 — giám sát, job nền, thẻ tài xế và Reset

## Phần đã triển khai

- **S-11 / T-23–T-25:** API cây trạm–trụ–đầu nối có lọc theo quyền sở hữu; lưới giám sát có nhãn trạng thái, thời điểm liên lạc cuối và cập nhật SSE; trình duyệt tự kết nối lại rồi tải lại trạng thái chuẩn.
- **S-12 / T-26:** job nền đánh dấu trụ quá hạn heartbeat là ngoại tuyến; màn hình suy trạng thái từ `last_seen_at` để vẫn đúng sau khi khởi động lại.
- **S-13 / T-28:** `ConnectionManager` thay kết nối cũ khi cùng mã trụ kết nối lại và đóng kết nối cũ.
- **S-14 / T-30–T-31:** lưu phản hồi OCPP theo cặp mã trụ/mã tin, trả lại phản hồi đã lưu khi phát lại, cảnh báo nếu cùng mã nhưng nội dung khác; job dọn bản ghi quá hạn.
- **S-15 / T-32–T-33:** migration và seed thẻ cho tài xế; `Authorize` phân biệt `Accepted`, `Blocked`, `Expired`, `Invalid`; log mã thẻ chỉ giữ bốn ký tự cuối.
- **S-16 / T-34–T-35:** lời gọi Reset từ máy chủ được ghép phản hồi theo message ID, có timeout, phân quyền và xử lý trạng thái trụ ngoại tuyến; simulator có thể nhận Reset và khởi động lại vòng kết nối.

## Giới hạn kiểm chứng

Test cục bộ xác nhận các luồng xử lý và quyền chính. Chưa có Docker Engine/staging để chạy bộ simulator theo các tiêu chí 20 trụ, kết nối ổn định, độ trễ hiển thị, khởi động lại tiến trình và kiểm thử Reset end-to-end. Vì vậy không ghi toàn bộ Sprint 2 là `Done`; các story và task cần các lần chạy ấy được để `In Progress` trong workbook rà soát.
