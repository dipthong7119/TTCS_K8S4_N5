# HỢP ĐỒNG API: BẮT ĐẦU SẠC TỪ XA (REMOTE START)
**Task**: T-51 (SCRUM-180) & SCRUM-193
**Backend phụ trách**: Hoàng Văn Đức
**Frontend tích hợp**: Đặng Ngọc Đại (SCRUM-190, 191, 192)
**Trạng thái**: Đã có API gửi lệnh và map phản hồi; chưa nghiệm thu đầy đủ T-51/S-24.

**Ghi chú sau đồng bộ vào f (06/10/2026):** Unit test của API đạt, nhưng chưa
kiểm đầu nối bận/trạm ngừng trước khi gửi, chưa ràng buộc thẻ ảo theo tài xế và
chưa lưu yêu cầu chờ 60 giây. Frontend hiện tại vẫn là bản thử, simulator fleet
chưa xử lý RemoteStart. Không coi phản hồi Accepted là phiên đã được tạo;
phiên chỉ xuất hiện khi máy chủ nhận StartTransaction hợp lệ từ trụ.

---

## 1. Đường dẫn API và Phương thức gọi

* **Đường dẫn (URL)**: `/api/charge_points/{code}/remote-start`
* **Phương thức (Method)**: `POST`
* **Xác thực / Quyền hạn**:
  - Gửi kèm Session Cookie của người dùng đã đăng nhập (`credentials: 'include'`).
  - Các vai trò (role) được phép gọi: `admin`, `operator`, `station_owner`, `driver`.

---

## 2. Dữ liệu phải gửi (Request Body)

* **Tham số trên URL**:
  - `code` (string): Mã nhận diện trụ sạc (ví dụ: `CP01`, `ST01-CP02`).

* **Tham số trong Body (JSON)**:
  - `connector_id` (int | null, tùy chọn): Số thứ tự đầu nối cần sạc (ví dụ: `1`, `2`). Nếu bỏ trống hoặc `null`, trụ sạc sẽ tự động chọn đầu nối khả dụng.
  - `id_tag` (string, bắt buộc): Mã thẻ RFID hoặc mã định danh tài xế (chuỗi từ 1 đến 20 ký tự, ví dụ: `"TAG12345"`).

### Ví dụ Request:
```http
POST /api/charge_points/CP01/remote-start HTTP/1.1
Content-Type: application/json

{
  "connector_id": 1,
  "id_tag": "TAG12345"
}
```

---

## 3. Ví dụ phản hồi thành công và lỗi

### 3.1. Phản hồi thành công (HTTP 200 OK)
Backend map phản hồi từ trụ về 2 trường hợp cụ thể:

* **Trường hợp 1: Trụ chấp nhận lệnh (`Accepted`)**
  ```json
  {
    "status": "Accepted",
    "message": "Trụ sạc đã chấp nhận lệnh bắt đầu sạc từ xa."
  }
  ```
  *(Frontend hiển thị thông báo thành công, chuyển sang trạng thái chờ trụ kích hoạt phiên sạc).*

* **Trường hợp 2: Trụ từ chối lệnh (`Rejected` - ví dụ: súng chưa cắm, đầu nối đang bận)**
  ```json
  {
    "status": "Rejected",
    "message": "Trụ sạc từ chối lệnh bắt đầu sạc từ xa (Rejected)."
  }
  ```
  *(Frontend hiển thị cảnh báo: Trụ từ chối lệnh bắt đầu sạc).*

---

### 3.2. Các phản hồi lỗi HTTP (Frontend cần bắt để hiển thị thông báo/toast)

* **HTTP 409 Conflict (Trụ ngoại tuyến hoặc mất kết nối)**:
  ```json
  {
    "detail": "Trụ sạc đang ngoại tuyến, không thể gửi lệnh."
  }
  ```
  hoặc
  ```json
  {
    "detail": "Trụ sạc đã ngắt kết nối trước khi nhận lệnh."
  }
  ```

* **HTTP 504 Gateway Timeout (Hết thời gian chờ)**:
  *(Xảy ra khi gửi lệnh qua WebSocket nhưng quá 30 giây trụ không phản hồi)*
  ```json
  {
    "detail": "Trụ không phản hồi lệnh RemoteStartTransaction trong thời gian chờ."
  }
  ```

* **HTTP 404 Not Found (Không tìm thấy trụ)**:
  ```json
  {
    "detail": "Không tìm thấy trụ sạc"
  }
  ```

* **HTTP 502 Bad Gateway (Lỗi giao thức OCPP)**:
  ```json
  {
    "detail": "Trụ từ chối lệnh RemoteStartTransaction."
  }
  ```
