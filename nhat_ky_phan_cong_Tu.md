# Nhật ký phân công công việc - Vy Hoàng Tú (Sprint 345)

**Thời gian cập nhật:** 09/10/2026
**Vai trò:** Frontend Developer (Mảng giao diện biểu giá, hoá đơn)

## 1. Danh sách nhiệm vụ hiện tại (Sprint 3)
- **SCRUM-61 (FE):** Màn hình khai báo biểu giá theo kWh và phí chiếm trụ (3 SP).
- **SCRUM-62 (FE):** Màn hình cấu hình nhiều khung giờ, cảnh báo chồng lấn/thiếu giờ (3 SP).
- **SCRUM-63 (Subtask FE: 208):** Hiển thị chi tiết cách tính tiền theo từng khung giờ cho phiên sạc (5 SP chung).
- **SCRUM-66 (FE):** Màn hình hoá đơn có diễn giải từng đoạn giá (3 SP).

*(Ghi chú: SCRUM-68 (FE) - Giao diện gói thuê bao đã được chuyển giao cho Phạm Văn Tuấn để giảm tải).*

## 2. Điều kiện bắt đầu làm việc (Dependencies)
Theo quy tắc chống nghẽn (Mục 6.1), Tú có thể bắt đầu làm việc ngay bằng cách sử dụng **Mock data** thay vì đợi Backend hoàn thành:

* **Đối với SCRUM-61, 62 (FE):** 
  - Đang chờ API biểu giá từ Hoàng Văn Tân và Trịnh Thanh Tùng.
  - **Hành động:** Chốt sớm hợp đồng API với Tân và Tùng, sau đó dùng dữ liệu giả (mock) để làm giao diện.
* **Đối với SCRUM-208, 66 (FE):** 
  - Đang chờ dữ liệu đoạn tính tiền (207, 66 BE) từ Tạ Như Vinh.
  - **Hành động:** Chốt sớm format hoá đơn với Vinh, sau đó sử dụng dữ liệu mock để tiếp tục công việc.

## 3. Hoạt động kiểm thử / Review chéo
- Nhận review/test từ: **Đặng Ngọc Đại**
- Người Tú cần review code: **Phạm Văn Tuấn** (đảm bảo review trong ngày khi có PR mở).

## 4. Ghi chú cá nhân
- Luôn ưu tiên chốt schema/hợp đồng API ngay từ đầu Sprint.
- Nếu bị chờ BE quá 1 ngày (dù đã hối thúc), báo cáo ngay cho Scrum Master (Trịnh Thanh Tùng) trong buổi Daily Scrum.

## 5. Tiến độ thực hiện (Cập nhật)
- **[Đã hoàn thành trước] SCRUM-61:** Đã dựng xong `form.html` (Màn hình khai báo biểu giá với Form nhập liệu kWh, phí chiếm trụ, tích hợp sẵn logic Mock Data khi submit).
- **[Đã hoàn thành trước] SCRUM-62:** Đã dựng xong `time_frames.html` (Màn hình cấu hình khung giờ động, bao gồm thuật toán bằng JavaScript để validate tính liền mạch 24h và chống chồng lấn các khung giờ).
- **Bước tiếp theo:**
  - Chờ API từ phía Backend để ghép vào các hàm Submit hiện tại.
  - Xin file JSON mẫu từ Backend để tiến hành render cho phần hóa đơn (SCRUM-66, 208).
