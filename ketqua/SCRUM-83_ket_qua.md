# SCRUM-83 — Hạn mức công suất theo khung giờ

## API contract

Các endpoint yêu cầu đăng nhập bằng cookie phiên. Vai trò `station_owner` chỉ được thao tác với trạm mình sở hữu; `admin` được phép theo quy ước của SCRUM-80.

| Method | Endpoint | Kết quả |
| --- | --- | --- |
| `GET` | `/api/stations/{station_id}/power-capacity-bands` | `200`, danh sách khung theo phút bắt đầu |
| `POST` | `/api/stations/{station_id}/power-capacity-bands` | `201`, khung vừa tạo |
| `PUT` | `/api/stations/{station_id}/power-capacity-bands/{band_id}` | `200`, khung sau cập nhật |
| `DELETE` | `/api/stations/{station_id}/power-capacity-bands/{band_id}` | `204` |

POST và PUT nhận cùng cấu trúc:

```json
{
  "start_minute": 1020,
  "end_minute": 1320,
  "power_limit_kw": "60.000"
}
```

`start_minute`/`end_minute` là số phút từ 00:00; `1440` biểu diễn 24:00. Ví dụ trên là 17:00–22:00. Khung qua nửa đêm dùng `end_minute < start_minute`, ví dụ 22:00–06:00 là `1320`–`360`. Khoảng giờ có biên kết thúc loại trừ: khung kế tiếp bắt đầu đúng giờ kết thúc của khung trước là hợp lệ.

Response mẫu:

```json
{
  "id": 12,
  "station_id": 3,
  "start_minute": 1020,
  "end_minute": 1320,
  "power_limit_kw": "60.000",
  "timezone_name": "Asia/Ho_Chi_Minh"
}
```

Mã lỗi: `401` chưa đăng nhập; `403` sai vai trò hoặc không sở hữu trạm; `404` không có trạm/khung; `409` khung bị chồng lấn hoặc trùng giờ bắt đầu; `422` giờ bắt đầu/kết thúc bằng nhau, giờ ngoài miền, hoặc công suất không dương/vượt định dạng `Numeric(10,3)`.

Phiên sạc đang chạy có thêm trường `requested_power_limit_w` trong API chi tiết phiên. Khi giới hạn yêu cầu đổi, SSE phát `session_update` với `session_id` và `requested_power_limit_w`; client có thể đọc số watt trực tiếp hoặc tải lại chi tiết phiên.

## Checklist kiểm tra thủ công — QA

1. Nâng schema bằng `alembic upgrade head`, đăng nhập bằng chủ trạm và gọi GET để xác nhận danh sách ban đầu rỗng.
2. Tạo khung 08:00–17:00 ở 80 kW và 17:00–22:00 ở 60 kW; GET phải trả cả hai theo giờ bắt đầu.
3. Thử khung chồng lấn 16:00–18:00 và khung 10:00–10:00; lần lượt nhận `409` và `422`. Thử `power_limit_kw` bằng 0 và số có hơn 3 chữ số thập phân; nhận `422`.
4. Tạo 22:00–06:00 rồi thử tạo khung 05:00–07:00; phải nhận `409`. Khung liền kề 06:00–10:00 phải được chấp nhận.
5. Dùng một chủ trạm khác gọi GET/POST/PUT/DELETE với `station_id` của trạm thử; mỗi thao tác phải bị từ chối `403`. Admin thao tác được theo chính sách SCRUM-80.
6. Đặt hạn mức mặc định 100 kW, cho hai phiên đang sạc hoạt động với đầu nối định danh 80 kW, rồi đặt khung hiện tại 100 kW. Xác nhận mỗi phiên nhận profile 50.000 W.
7. Sửa khung hiện tại xuống 60 kW. Trong tối đa 30 giây, mỗi phiên phải nhận profile 30.000 W; tổng hai giới hạn không vượt 60.000 W. Driver và chủ trạm nhận `session_update` có watt mới; client tải chi tiết phiên thấy cùng giá trị.
8. Với khung 08:00–17:00 và 17:00–22:00, kiểm tra ngay trước/sau 17:00 theo giờ trả về trong `timezone_name`; job cập nhật các phiên đang chạy trong tối đa 30 giây dù không có xe vào/rời.
9. Xóa khung đang áp dụng; trạm quay về `power_limit_kw` mặc định và các phiên được phân bổ lại theo giới hạn đó. Chạy lại job khi giới hạn không đổi, không được gửi profile lặp.

## Kết quả kiểm tra

- SCRUM-83 và SCRUM-80/81/82: `12 passed` ở lượt focused cuối.
- Toàn bộ pytest backend và test gốc: `930 passed, 4 skipped`; 2 ca Docker acceptance không chạy được vì Docker Desktop daemon không hoạt động (`dockerDesktopLinuxEngine` pipe không tồn tại). Một test timezone bổ sung được chạy trong lượt focused sau đó.
- Migration `alembic upgrade head` chạy thành công trên SQLite trong bộ nhớ; SCRUM-83 là Alembic head hiện tại.
- Ruff: đạt. Mypy: đạt (`80 source files`).

## Ghi chú triển khai

- Hạn mức khung dùng `Numeric(10,3)` kW như SCRUM-80; không thêm cột vào bảng trạm, trụ, đầu nối hoặc phiên sạc.
- Nếu trạm chưa có hạn mức mặc định và đang ở ngoài khung, hệ thống khôi phục giới hạn yêu cầu về mức định danh từng đầu nối; nếu trạm chưa có cả mặc định lẫn khung thì giữ hành vi cũ, không cấp profile trạm.
- Múi giờ lấy từ biểu giá non-demo mới nhất của trạm; nếu chưa có biểu giá thì dùng `Asia/Ho_Chi_Minh`, cùng cách chọn múi giờ ở API doanh thu trạm.
- Job khởi chạy cùng app, quét phiên đang hoạt động mỗi 30 giây và phục hồi phân bổ hiện tại khi app khởi động lại. Khóa theo trạm trong tiến trình và `SELECT FOR UPDATE` trên trạm cùng kiểm tra giới hạn đã lưu giúp các lượt chạy lặp thành no-op.
- SSE subscribers hiện lưu trong bộ nhớ tiến trình, giống SCRUM-97. Triển khai nhiều worker/replica cần broker dùng chung để chuyển sự kiện SSE; kiến trúc hiện tại của repo cũng yêu cầu một tiến trình cho connection manager OCPP.
