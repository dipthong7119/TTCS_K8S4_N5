# Kế hoạch Sprint 3 - Ngô Quang Tùng (Backend)

Dựa trên tài liệu phân công Sprint 3, dưới đây là bản tóm tắt kế hoạch làm việc, lịch trình và các trách nhiệm dành riêng cho bạn.

## 1. Thông tin chung
- **Vai trò:** Backend
- **Tổng khối lượng:** 8 Story Points (SP)
- **Đánh giá mức độ:** Bạn đang nắm giữ **đường găng (critical path)** của cả sprint. Các task nền tảng của bạn (đặc biệt là T-36) rất quan trọng và nhiều người trong team đang phụ thuộc vào nó.

## 2. Chi tiết công việc (Tasks)
Bạn chịu trách nhiệm chính triển khai 4 task sau:
1. **T-36 (SCRUM-161):** Bảng `charging_sessions` + migration (2 SP)
2. **T-37 (SCRUM-162):** Handler `StartTransaction` (2 SP)
3. **T-38 (SCRUM-163):** Handler `StopTransaction` (2 SP)
4. **SCRUM-189 (thuộc T-39):** Tích hợp hàm kWh vào luồng `StopTransaction` (2 SP)

*(Người review code cho bạn sẽ là **Nguyễn Lâm Tùng**).*

## 3. Trách nhiệm Review
Bạn được phân công làm người duyệt code (Reviewer) cho các task của **Nguyễn Lâm Tùng** và **Hoàng Văn Đức**, để đảm bảo góc nhìn chéo:
- **Nguyễn Lâm Tùng:** T-40, T-41, T-42, T-44 (Nhóm tính năng số đo - MeterValues).
- **Hoàng Văn Đức:** T-49, T-51, SCRUM-193 (Nhóm tính năng điều khiển từ xa Start/Stop).

## 4. Lịch trình triển khai gợi ý (Sprint 10 ngày)
- **Ngày 1:** T-36 (Tập trung làm và **merge migration sớm nhất có thể**).
- **Ngày 2:** Hoàn thiện T-36 / Bắt đầu T-37.
- **Ngày 3:** T-37.
- **Ngày 4 - Ngày 5:** T-38.
- **Ngày 6 - Ngày 7:** SCRUM-189.
- **Ngày 8:** Review code cho các thành viên khác / Fix bugs.
- **Ngày 9 - Ngày 10:** Quỹ thời gian dự phòng (Buffer) / Sửa lỗi phát sinh khi tích hợp kịch bản 20 trụ.

## 5. Phụ thuộc & Quy tắc phối hợp
- **Tránh chặn luồng (Blocker):** Bạn cần hoàn thành và merge T-36 (Bảng phiên) ngay trong **ngày 1-2**. Các thành viên khác như Đức (T-49) và Tân (T-47) đang phải đợi bảng này để làm việc.
- **Làm chủ mã nguồn:** File/handler liên quan đến `StartTransaction` và `StopTransaction` do **bạn làm chủ**. Bất kỳ ai muốn sửa đều phải nhờ bạn hoặc tạo PR nhỏ để bạn duyệt.
- **Sự phụ thuộc vào người khác:** Task SCRUM-189 của bạn cần hàm tính kWh từ Tân (SCRUM-187). Tân sẽ bắt đầu làm việc này ngay từ ngày 1 nên dự kiến sẽ xong trước khi bạn cần đến (vào ngày 6).
- **Quy tắc review:** Hãy nhờ Lâm Tùng review nhanh các PR của mình để tránh bị ùn ứ, do công việc của bạn là cốt lõi của sprint.

Chúc bạn có một Sprint 3 hiệu quả và thành công!
