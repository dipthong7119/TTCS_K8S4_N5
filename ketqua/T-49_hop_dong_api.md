# HỢP ĐỒNG API: DỪNG SẠC TỪ XA (REMOTE STOP)
**Task**: T-49 (SCRUM-172) & S-23
**Backend phụ trách**: Hoàng Văn Đức
**Frontend tích hợp**: Phạm Văn Tuấn (T-50: Nút dừng trên màn hình phiên)
**Trạng thái**: Đã sẵn sàng trên nhánh `HOANG-DUC`

**Ghi chú sau đồng bộ vào f (06/10/2026):** API và các nhánh lỗi đã kiểm thử
đơn vị; simulator fleet hiện chưa xử lý RemoteStop nên chưa nghiệm thu thành
công đầu cuối trên fleet. Luồng chờ StopTransaction và job quá 2 phút đã có
trước đợt gộp này; nhánh bổ sung xử lý lỗi chi tiết và bằng chứng kiểm thử.

---

## 1. Đường dẫn API và Phương thức gọi

* **Đường dẫn (URL)**: `/api/sessions/{session_id}/remote-stop`
* **Phương thức (Method)**: `POST`
* **Xác thực / Quyền hạn**:
  - Gửi kèm Session Cookie của người dùng đã đăng nhập (`credentials: 'include'`).
  - Các vai trò (role) được phép gọi: `admin`, `operator`. (Tài xế/Driver không được phép dừng từ xa qua nút vận hành, trả HTTP 403).

---

## 2. Tham số truyền vào

* **Tham số trên URL**:
  - `session_id` (int): ID của phiên sạc cần dừng (ví dụ: `101`, `102`).
* **Body**: Rỗng (`{}`).

### Ví dụ Request:
```http
POST /api/sessions/101/remote-stop HTTP/1.1
Content-Type: application/json
```

---

## 3. Quy ước hoạt động quan trọng (S-23 / T-49)

> **LƯU Ý CỐT LÕI**: Khi trụ sạc trả về `Accepted`, hệ thống **chưa đóng phiên ngay lập tức**! Phiên sạc sẽ chỉ đóng chính thức khi trụ gửi tin nhắn `StopTransaction` thật (kèm lý do `Remote` và số đo cuối `meterStop`).
> Frontend sau khi nhận phản hồi HTTP 200 `Accepted` cần hiển thị trạng thái chờ (ví dụ: spinner / đồng hồ đếm ngược tối đa 2 phút) và lắng nghe sự kiện SSE cập nhật phiên chuyển sang `completed`. Nếu sau 2 phút trụ không gửi `StopTransaction`, job nền hệ thống sẽ tự động chuyển phiên sang `needs_review`.

---

## 4. Phản hồi thành công và các mã lỗi

### 4.1. Phản hồi thành công (HTTP 200 OK)
Trụ sạc trực tuyến và chấp nhận lệnh dừng từ xa (`Accepted`):
```json
{
  "status": "Accepted",
  "message": "Đã gửi lệnh; phiên sẽ đóng khi trụ báo StopTransaction."
}
```
*(Frontend hiển thị thông báo: Đã gửi lệnh dừng tới trụ, đang chờ trụ ngắt dòng sạc...)*

---

### 4.2. Các phản hồi lỗi HTTP (Frontend cần bắt để hiển thị thông báo/toast tương ứng theo AC của T-50)

* **Trường hợp 1: Trụ sạc từ chối lệnh dừng (`Rejected`)** -> HTTP 502 Bad Gateway:
  ```json
  {
    "detail": "Trụ không chấp nhận lệnh dừng từ xa (Rejected)."
  }
  ```
  *(Frontend hiển thị toast lỗi: Trụ từ chối lệnh dừng, phiên vẫn tiếp tục sạc).*

* **Trường hợp 2: Trụ sạc ngoại tuyến hoặc mất kết nối** -> HTTP 409 Conflict:
  ```json
  {
    "detail": "Trụ sạc đang ngoại tuyến, không thể gửi lệnh dừng."
  }
  ```
  hoặc (nếu ngắt kết nối giữa chừng):
  ```json
  {
    "detail": "Trụ sạc đã ngắt kết nối trước khi nhận lệnh dừng."
  }
  ```
  *(Frontend hiển thị toast cảnh báo: Trụ sạc ngoại tuyến, không thể gửi lệnh).*

* **Trường hợp 3: Phiên sạc đã kết thúc trước đó** -> HTTP 409 Conflict:
  ```json
  {
    "detail": "Phiên sạc đã kết thúc, không thể dừng từ xa"
  }
  ```

* **Trường hợp 4: Hết thời gian chờ phản hồi từ trụ** -> HTTP 504 Gateway Timeout:
  ```json
  {
    "detail": "Trụ không phản hồi lệnh dừng từ xa trong thời gian chờ."
  }
  ```
  *(Frontend hiển thị toast lỗi: Hết thời gian chờ phản hồi từ trụ).*

* **Trường hợp 5: Không tìm thấy phiên sạc** -> HTTP 404 Not Found:
  ```json
  {
    "detail": "Không tìm thấy phiên sạc"
  }
  ```

* **Trường hợp 6: Không đủ quyền truy cập** -> HTTP 403 Forbidden:
  ```json
  {
    "detail": "Yêu cầu quyền admin hoặc operator"
  }
  ```
