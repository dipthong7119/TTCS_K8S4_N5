# SCRUM-191, SCRUM-192, SCRUM-194 — Đặng Ngọc Đại

Ngày: 07/10/2026. Phạm vi: Frontend T-52, kế thừa SCRUM-190 trên main b1f0f11.
Nhánh: `DANG-DAI-SCRUM-191-192-194` tại `D:\TTCS_K8S4_N5`.

## Kết quả triển khai

- SCRUM-191: gửi RemoteStart qua ApiClient; vô hiệu nút, đầu nối và mã thẻ khi chờ; giới hạn tổng thời gian 60 giây kể từ bấm nút, kể cả thời gian gửi lệnh. Accepted chỉ xác nhận nhận lệnh. Kiểm tra phiên thật mỗi 2 giây; yêu cầu đúng trụ, đầu nối và thời điểm phiên mới. Giữ trạng thái khi drawer vẽ lại/SSE cập nhật. Hủy HTTP khi hết hạn; bỏ qua phản hồi cũ kể cả khi đã thử lại.
- SCRUM-192: thông báo riêng khi trụ từ chối (gợi ý kiểm tra súng/thẻ), đầu nối bận, hết thời gian; giữ thông báo ngoại tuyến và lỗi mạng đúng nghĩa; cho phép thử lại sau thất bại.
- SCRUM-194: kiểm thử mã JS thật bằng DOM/API giả lập, đồng hồ điều khiển được; có ca 60 giây, phản hồi muộn, thử lại, không gửi trùng, kiểm tra phiên, API payload, mã thẻ và phân quyền điều hướng.

## Kiểm chứng

`node --test tests/frontend_behavior.cjs`: **63 pass, 0 fail**.
`git diff --check`: đạt (cảnh báo LF/CRLF chỉ là quy ước xuống dòng Windows).
Các ca frontend cũ được chạy cùng các ca mới để kiểm tra hồi quy.

## Phụ thuộc còn thiếu để nghiệm thu S-24/T-52 đầy đủ

1. Backend hiện yêu cầu `id_tag` trong request; UI nhập thẻ RFID đã cấp, tối đa 20 ký tự. Backend chưa tự lấy thẻ ảo từ tài xế như đặc tả T-51. Không tự tạo mã thẻ hay lấy email làm thẻ.
2. Route trang `/monitoring` hiện chỉ cho admin/operator/station_owner. Tài xế chỉ có role driver chưa mở được trang này. Logic FE chuyển sang `/sessions/mine` khi xác nhận phiên của tài xế đã được kiểm thử; cần người phụ trách backend xác định trang chi tiết trụ cho tài xế và quyền dữ liệu phù hợp.
3. API RemoteStart trên main chưa kiểm đầu nối bận/đặt chỗ và trạm hoạt động theo AC T-51. FE chặn đầu nối đang không Available và xử lý HTTP 409, nhưng kiểm tra tại server thuộc Đức (SCRUM-193/T-51).
4. Vận hành viên/admin dùng danh sách phiên được backend cho phép xem, tối đa 100 phiên active gần nhất; xác nhận phiên rồi chuyển `/audit`. Chủ trạm ở lại trang chi tiết vì không có quyền `/audit`. Mạng/server chậm có thể làm chưa xác nhận được phiên; UI không giả lập thành công.
5. Chưa chạy nghiệm thu với trụ ảo thật, staging/CI, hay kiểm tra trực quan trên trình duyệt. `docker` không có trong PATH của phiên này. Kết quả trên là kiểm thử hành vi tự động, không thay thế nghiệm thu S-24.

Vì các phụ thuộc trên, **chưa đánh dấu Done toàn bộ SCRUM-194/S-24** và chưa có review của Phạm Văn Tuấn.
Không thay đổi backend của Đức, không push hay merge main.

## Chạy kiểm thử

Trong terminal tại `D:\TTCS_K8S4_N5` trên nhánh ở trên:

```powershell
node --test tests/frontend_behavior.cjs
git diff --check
```

Nếu `node` chưa có trong PATH:

```powershell
& 'C:\Users\NGOC DAI\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test tests/frontend_behavior.cjs
```

## Kiểm thử thủ công để nghiệm thu với trụ ảo

Chuẩn bị tài khoản phù hợp, thẻ hợp lệ đã có trong database, trụ online, đầu nối Available và backend hỗ trợ AC T-51. Không dùng thẻ giả để nghiệm thu luồng thành công.

| Ca | Thao tác | Kết quả cần quan sát |
| --- | --- | --- |
| Bắt đầu thành công | Chọn đầu nối, nhập thẻ, bấm bắt đầu; trụ Accepted rồi StartTransaction | Nút khóa, chờ phiên thật, xác nhận phiên đúng trụ/đầu nối; driver sang màn hình phiên |
| Chỉ Accepted | Trụ nhận lệnh nhưng không gửi StartTransaction | Sau tối đa 60 giây hiện hết thời gian, không báo sạc thành công, cho thử lại |
| Rejected | Cấu hình trụ từ chối | Hiện từ chối và gợi ý kiểm tra súng/thẻ; mở khóa thao tác |
| Trụ bận | Đầu nối không Available hoặc API trả 409 | Không chọn được đầu nối bận; nếu server trả 409 thì hiện bận |
| Mất mạng | Ngắt mạng khi gửi | Hiện lỗi mạng hoặc hết thời gian; không treo nút quá 60 giây |
| Bấm trùng | Bấm liên tục, đóng/mở drawer trong lúc chờ | Chỉ một lệnh; trạng thái chờ còn giữ |
| Phản hồi muộn | Cho lần đầu hết hạn, thử lại rồi trả phản hồi lần đầu | Phản hồi lần đầu không làm đổi lần thử lại |
| SSE cập nhật | Gửi status_update trong lúc chờ | Drawer vẽ lại vẫn giữ khóa và thông báo |
| Phiên không khớp | Trả phiên cũ/khác trụ/khác đầu nối | Không điều hướng, không báo bắt đầu thành công |
| Điện thoại | Mở ở bề rộng 360px, chọn đầu nối và nhập thẻ | Điều khiển và thông báo đọc được, không tràn ngang |

Ghi kết quả thực tế, phiên/trace OCPP và bằng chứng trước khi chuyển Jira sang Done; hiện bảng trên là kịch bản, chưa phải bằng chứng đã chạy.
