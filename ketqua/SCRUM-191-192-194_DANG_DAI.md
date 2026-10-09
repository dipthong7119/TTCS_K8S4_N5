# SCRUM-191, SCRUM-192, SCRUM-194 — Đặng Ngọc Đại

Ngày: 07/10/2026. Phạm vi: Frontend T-52, kế thừa SCRUM-190 trên main b1f0f11.
Nhánh: `DANG-DAI-SCRUM-191-192-194` tại `D:\TTCS_K8S4_N5`.

## Kết quả triển khai

- SCRUM-191: gửi RemoteStart qua ApiClient; vô hiệu nút, đầu nối và mã thẻ khi chờ; giới hạn tổng thời gian 60 giây kể từ bấm nút, kể cả thời gian gửi lệnh. Accepted chỉ xác nhận nhận lệnh. Kiểm tra phiên thật mỗi 2 giây; yêu cầu đúng trụ, đầu nối và thời điểm phiên mới. Giữ trạng thái khi drawer vẽ lại/SSE cập nhật. Khôi phục đầy đủ đầu nối đã chọn và mã thẻ RFID đã nhập khi đóng/mở lại bảng chi tiết bằng dấu × trong lúc đang chờ. Hủy HTTP khi hết hạn; bỏ qua phản hồi cũ kể cả khi đã thử lại. Dọn dẹp timer và abort request khi `pagehide` (rời trang).
- SCRUM-192: thông báo riêng khi trụ từ chối (gợi ý kiểm tra súng/thẻ), đầu nối bận, hết thời gian; giữ thông báo ngoại tuyến và lỗi mạng đúng nghĩa; cho phép thử lại sau thất bại.
- SCRUM-194: kiểm thử mã JS thật bằng DOM/API giả lập, đồng hồ điều khiển được; có ca 60 giây, phản hồi muộn, thử lại, không gửi trùng, kiểm tra phiên, API payload, mã thẻ, đóng/mở lại bảng chi tiết trong lúc chờ, dọn dẹp timer khi rời trang và phân quyền điều hướng.

## Kiểm chứng tự động

`node --test tests/frontend_behavior.cjs`: **65 pass, 0 fail**.
`git diff --check`: đạt (cảnh báo LF/CRLF chỉ là quy ước xuống dòng Windows).
Tất cả các ca frontend cũ được chạy cùng các ca mới để đảm bảo không hồi quy.

### Các ca kiểm thử tự động chính:
- `SCRUM-191: blocks duplicate commands, survives drawer rerender and waits after Accepted`: Đạt.
- `SCRUM-191: timeout ignores a late Accepted response and never navigates`: Đạt.
- `SCRUM-191: an old response after timeout cannot finish or replace a retry`: Đạt.
- `SCRUM-192: Rejected suggests checking cable and allows retry`: Đạt.
- `SCRUM-192: API error 409 releases controls`: Đạt (thông báo trụ/đầu nối bận).
- `SCRUM-192: API error 504 releases controls`: Đạt (thông báo hết thời gian chờ).
- `SCRUM-192: API error 502 releases controls`: Đạt (thông báo trụ từ chối).
- `SCRUM-192: API error 0 releases controls`: Đạt (thông báo lỗi mạng).
- `SCRUM-194: only a new session on the chosen point and connector navigates to T-48`: Đạt.
- `SCRUM-194: operator uses visible session list and navigates to audit only after real session`: Đạt.
- `SCRUM-194: station owner stays on permitted detail page after session starts`: Đạt.
- `SCRUM-194: busy/offline connectors and missing or oversized tags cannot send a command`: Đạt.
- `SCRUM-194: remote start API encodes code and sends connector, tag and cancellation signal`: Đạt.
- `SCRUM-194: closing and reopening drawer during pending request preserves connector, tag and waiting state`: Đạt.
- `SCRUM-194: leaving page (pagehide) clears pending timers and aborts in-flight request`: Đạt.

## Kết quả kiểm tra thủ công trên trình duyệt (07/10/2026)

Thực hiện kiểm tra thực tế trên trình duyệt với backend CSMS và OCPP Simulator Fleet đang chạy cục bộ tại `http://localhost:8000`:

1. **Hiển thị trạng thái chờ sau khi bấm bắt đầu sạc:**
   - Mở trạm Vincom Center, chọn trụ `CP_VINCOM_01`, chọn Đầu nối 1, nhập mã `TEST-TAG` và bấm "Bắt đầu sạc".
   - Kết quả: Nút chuyển sang `Đang chờ bắt đầu sạc…` và bị vô hiệu hóa cùng dropdown đầu nối và ô thẻ; xuất hiện dòng thông báo *"Đang gửi yêu cầu bắt đầu sạc. Chờ tối đa 60 giây…"*.
2. **Đóng rồi mở lại bảng chi tiết trong lúc đang chờ (Kết quả lịch sử ngày 07/10/2026):**
   - **Nguồn kiểm chứng**: Được ghi nhận từ commit `8d9b4db` (*fix(SCRUM-191,194): preserve RFID when reopening charging drawer*) và ca kiểm thử tự động tương ứng trong `tests/frontend_behavior.cjs`.
   - Trong khi đang ở trạng thái chờ, bấm dấu `×` để đóng bảng chi tiết, sau đó bấm mở lại thẻ trạm Vincom Center.
   - Kết quả: Đầu nối 1 vẫn được chọn (disabled), ô mã thẻ RFID vẫn hiển thị đầy đủ `TEST-TAG` (disabled, không bị mất/trống), nút vẫn ở trạng thái `Đang chờ bắt đầu sạc…` (disabled, chống bấm trùng), và dòng thông báo chờ vẫn được giữ nguyên.
   - *Lưu ý*: Đây là kết quả lịch sử của ngày 07/10/2026, chưa được chạy lại trong đợt kiểm thử hôm nay (09/10/2026).
3. **Khi hết thời gian chờ:**
   - Chờ đến khi hết hạn thời gian chờ.
   - Kết quả: Giao diện hiển thị đúng thông báo hết thời gian chờ; nút "Bắt đầu sạc" được mở khóa trở lại; mã thẻ `TEST-TAG` và đầu nối đã chọn vẫn được giữ nguyên để có thể bấm thử lại ngay mà không phải nhập lại.

### Giới hạn ghi nhận trong đợt kiểm tra thủ công (07/10/2026):
- **Thời lượng chờ:** Chưa đo chính xác thời lượng 60 giây bằng đồng hồ bấm giờ (chỉ quan sát có thời gian chờ và thông báo hết thời gian kích hoạt).
- **Các tình huống chưa kiểm tra thủ công:** Chưa kiểm tra thủ công các tình huống trụ từ chối (Rejected), trụ bận (409) và bắt đầu phiên thành công. Các tình huống này hiện chỉ có bằng chứng xác nhận qua kiểm thử tự động tương ứng trong `tests/frontend_behavior.cjs`.
- **Phụ thuộc trụ ảo:** Luồng bắt đầu phiên thành công hoàn chỉnh từ xa với trụ ảo thật vẫn phụ thuộc vào việc simulator/backend hỗ trợ đầy đủ lệnh `RemoteStartTransaction` (T-51/T-55), do fleet ảo hiện tại mặc định chưa tự phát `StartTransaction` khi nhận RemoteStart.

## Kết quả kiểm tra thủ công trên trình duyệt (09/10/2026)

Thực hiện kiểm tra thực tế trên trình duyệt với backend CSMS đang chạy tại `http://localhost:8000` và trụ ảo `CP_VINCOM_01` kết nối qua simulator cục bộ:

1. **Kiểm tra với vai trò Vận hành viên (Operator — `operator@csms.local`):**
   - Mở màn hình `/monitoring`: Trụ `CP_VINCOM_01` hiển thị trực tuyến (online) sau khi khởi động simulator.
   - Mở drawer chi tiết trạm Vincom Center, chọn Đầu nối 1, nhập mã thẻ RFID mẫu `DEMO-DRIVER-0005`.
   - Bấm "Bắt đầu sạc":
     + Giao diện chuyển sang trạng thái chờ: nút chuyển sang `Đang chờ bắt đầu sạc…` và bị vô hiệu hóa cùng dropdown đầu nối và ô thẻ; hiển thị thông báo chờ.
     + Sau đó hệ thống hiển thị thông báo trụ chưa phản hồi (*"Hết thời gian chờ, trụ chưa phản hồi. Kiểm tra trạng thái trước khi thử lại."* — do simulator hiện tại chưa có handler xử lý lệnh `RemoteStartTransaction` dẫn đến timeout phía máy chủ).
     + Nút "Bắt đầu sạc" được mở khóa trở lại; Đầu nối 1 và mã thẻ `DEMO-DRIVER-0005` được giữ nguyên để có thể bấm thử lại.
2. **Kiểm tra với vai trò Tài xế (Driver — `driver@csms.local`):**
   - Đăng nhập thành công với tài khoản Driver, hệ thống tự động chuyển hướng đến `/sessions/mine` (màn hình *Phiên sạc của tôi*).
   - Tại banner chưa có phiên sạc, bấm nút "Tìm trạm sạc": trình duyệt điều hướng đến `/stations` và nhận thông báo lỗi `{"detail":"Không có quyền truy cập"}` (HTTP 403 do route `/stations` chỉ dành cho admin/station_owner/operator).
3. **Các giới hạn ghi nhận trong đợt kiểm tra hôm nay:**
   - Chưa xác nhận được luồng bắt đầu sạc thành công (tạo phiên sạc thật trong cơ sở dữ liệu).
   - Chưa đo thời gian chờ chính xác bằng đồng hồ bấm giờ.
   - Chưa kiểm tra thủ công các tình huống lỗi trụ bận (HTTP 409) và trụ từ chối (`Rejected` / HTTP 502).
   - Đợt kiểm tra hôm nay chưa thực hiện lại bước đóng/mở drawer bằng dấu `×` trong lúc đang chờ (kết quả này là kết quả lịch sử của ngày 07/10 gắn với commit `8d9b4db`).
4. **Phân biệt với kiểm thử tự động:**
   - Kết quả kiểm tra thủ công thực tế trên giao diện hôm nay được ghi nhận độc lập, phân biệt rõ với bộ kiểm thử tự động 68/68 test JS pass đã ghi trong nhật ký.
5. **Hiện trạng SCRUM-194:**
   - SCRUM-194 hiện ở Done trên Jira. PR #35 và #43 đã merge theo nhật ký Jira. Các vấn đề phát hiện ngày 09/10 gồm CP_VINCOM_01 timeout và Driver bị chặn khi bấm Tìm trạm sạc đang chờ nhóm xác nhận phạm vi và hướng xử lý.

## Phụ thuộc còn thiếu để nghiệm thu S-24/T-52 đầy đủ

1. Backend hiện yêu cầu `id_tag` trong request; UI nhập thẻ RFID đã cấp, tối đa 20 ký tự. Backend chưa tự lấy thẻ ảo từ tài xế như đặc tả T-51. Không tự tạo mã thẻ hay lấy email làm thẻ. Đây là phụ thuộc kỹ thuật cần xác nhận và phối hợp với Hoàng Văn Đức theo đúng đặc tả T-51.
2. Route trang `/monitoring` hiện chỉ cho admin/operator/station_owner. Tài xế chỉ có role driver chưa mở được trang này. Logic FE chuyển sang `/sessions/mine` khi xác nhận phiên của tài xế đã được kiểm thử; cần người phụ trách backend xác định trang chi tiết trụ cho tài xế và quyền dữ liệu phù hợp.
3. API RemoteStart trên main chưa kiểm đầu nối bận/đặt chỗ và trạm hoạt động theo AC T-51. FE chặn đầu nối đang không Available và xử lý HTTP 409, nhưng kiểm tra tại server thuộc Đức (SCRUM-193/T-51).
4. Vận hành viên/admin dùng danh sách phiên được backend cho phép xem, tối đa 100 phiên active gần nhất; xác nhận phiên rồi chuyển `/audit`. Chủ trạm ở lại trang chi tiết vì không có quyền `/audit`. Mạng/server chậm có thể làm chưa xác nhận được phiên; UI không giả lập thành công.
5. Chưa chạy nghiệm thu tích hợp đầy đủ với trụ ảo thật trong môi trường CI/staging.

SCRUM-194 hiện ở Done trên Jira. PR #35 và #43 đã merge theo nhật ký Jira. Các vấn đề phát hiện ngày 09/10 gồm CP_VINCOM_01 timeout và Driver bị chặn khi bấm Tìm trạm sạc đang chờ nhóm xác nhận phạm vi và hướng xử lý.
Không thay đổi backend của Đức, chưa commit và chưa push hay merge main.

## Chạy kiểm thử

Trong terminal tại `D:\TTCS_K8S4_N5`:

```powershell
node --test tests/frontend_behavior.cjs
git diff --check
```

Nếu `node` chưa có trong PATH:

```powershell
& 'C:\Users\NGOC DAI\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --test tests/frontend_behavior.cjs
git diff --check
```
