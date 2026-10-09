# Đồng bộ toàn bộ nhánh GitHub và chuẩn bị kiểm thử — 09/10/2026

Repository: `dipthong7119/TTCS_K8S4_N5`.
Nhánh local bàn giao: `codex/integration-all-branches-20261009`.
Base GitHub `main`: `1a09e9c`. Commit code sau xử lý tích hợp: `95077ea`.
Các commit tài liệu sau đó không thay đổi code đã kiểm thử.

## Lịch sử được giữ

Đã fetch lại trong lúc làm để nhận cả các push mới của Đặng Đại và Phạm Tuấn.
Tất cả 13 đầu nhánh dưới đây là tổ tiên của nhánh bàn giao, được xác nhận bằng
`git merge-base --is-ancestor`. Merge giữ nguyên SHA và tác giả, không squash/rebase.

| Nhánh nguồn | Đầu nhánh đã nhận |
| --- | --- |
| main | 1a09e9c |
| sprint-3 | 58a4c07 |
| TRINH-TUNG | 86a1147 |
| NGO-TUNG | d661310 |
| LAM-TUNG | 1dfe4a2 |
| HOANG-DUC | 083a99e |
| HOANG-TAN | d12fd20 |
| DANG-DAI | ad5a0c9 |
| DANG-DAI-SCRUM-191-192-194 | b7e7ae1 |
| DANG-DAI-merge-main-191-192-194 | 40f8c22 |
| PHAM-TUAN | 3975113 |
| TA-VINH | 1806e8c |
| VY-TU | d3e6800 |

GitHub force-push HOANG-TAN từ `37783c1` sang `d12fd20`: đầu cũ được giữ ở
`codex/backup-hoang-tan-before-force-20261009`. GitHub cũng force-push PHAM-TUAN
từ `3113070` sang `3975113`; cả commit cũ lẫn đầu mới đều đã có trong lịch sử nhánh
bàn giao. Nhánh nguồn trên GitHub được giữ như lúc fetch.

Hai thay đổi chưa commit của người dùng được lưu bằng stash có nhãn
`codex-preserve-user-docs-before-all-branch-sync-20261009`, rồi áp lại vào working
tree sau các commit đồng bộ: workbook Excel trong `huongdan` được sửa và
`huongdan/Phan_cong_Sprint3.md` được xóa. Chúng không nằm trong commit tích hợp.

## Thay đổi và xử lý xung đột

- Nhận cấu hình OCPP của LAM-TUNG, biểu giá/phí chiếm trụ và thuật toán tính tiền
  của HOANG-TAN, sandbox ví và simulator RemoteStart/Stop của HOANG-DUC.
- Giữ bộ đáp án SCRUM-65 của TRINH-TUNG, các commit Sprint 3, code/QA của những
  nhánh cũ và báo cáo mới của DANG-DAI/PHAM-TUAN.
- Với xung đột nhánh cũ DANG-DAI, giữ UI remote-start 60 giây hiện tại đã có kiểm
  thử, UTC hiện tại và chỉ một khai báo API. Simulator lấy bản HOANG-DUC mới có
  StartTransaction/StopTransaction thật.
- Nhật ký vẫn ở `ketqua/nhat_ky.md`, giữ các bản ghi từ các nguồn; không hồi sinh
  đường dẫn `nhat_ky.md` cũ ở root. Kết quả QA mới không bị thay bằng bảng cũ.
- Thêm migration merge `h20261009_merge_sync` nối cấu hình, biểu giá và thanh toán;
  giữ các revision gốc. Thêm `h20261009_wallet_types` để constraint DB thật cho phép
  `sandbox_topup`/`refund`, đồng thời giữ ràng buộc dấu của số tiền. Trước sửa, model
  mới cho phép nhưng DB nâng cấp từ migration cũ sẽ từ chối nạp sandbox.
- Sửa mock cấu hình nhận keyword `timeout`, typecheck phản hồi không phải chuỗi,
  và các test nhịp tim patch `app.config.settings` sau refactor.
- SCRUM-65-17: giữ các đoạn giá bằng 0 khi phiên không tiêu thụ điện, đúng đáp án
  tính tay và phần diễn giải hóa đơn.
- SCRUM-184: dùng ApiClient mới của PHAM-TUAN; giữ kiểm tra danh sách trụ, không
  báo đối chiếu mẫu thành công khi inventory rỗng/lỗi hoặc API mất kết nối. Test
  frontend gọi ApiClient thật qua HTTP stub, có thêm ca lỗi mạng.

## Kết quả kiểm tra

| Kiểm tra | Kết quả |
| --- | --- |
| Pytest theo nhóm CI, có coverage, không gồm file nghiệm thu Docker 20 trụ | 601 passed, 5 skipped |
| Frontend Node | 82 passed, 0 failed |
| Tài nguyên/frontend page backend sau cập nhật frontend cuối | 19 passed |
| Migration trên PostgreSQL thật | 12 passed |
| Ruff toàn phạm vi CI | Đạt |
| Mypy | Đạt, 52 file |
| pip-audit local | Không phát hiện lỗ hổng đã biết |
| Build image bản gộp | Đạt |
| Docker/OCPP smoke và ca 3 trụ | 11 passed |
| Gate 20 trụ, 3 lượt seed 42/43/44 | PASS, 20/20 MATCH mỗi lượt, 0 thiếu/lệch/trùng |
| Alembic heads | Một head: h20261009_wallet_types |
| SQLite local hiện có | Nâng cấp thành công, giữ số lượng user/trạm/trụ/phiên/giao dịch |
| Lịch sử nguồn | 13/13 đầu nhánh là ancestor của HEAD |

Log/JUnit local nằm trong `outputs/sprint3-ci/integration-20261009/`. Runner 20
trụ tạo thêm thư mục theo lượt, có `manifest.json`, báo cáo JSON/Markdown và log.
Image kiểm tra cuối: `csms-app:integration-final-20261009`, build từ code `95077ea`.
Các stack Docker thử nghiệm được tạo riêng và dọn sau khi chạy, không dùng DB web.

SQLite local đã được sao lưu ở
`outputs/sprint3-ci/integration-20261009/csms-before-sync.db` trước khi nâng từ
`h20261004_defaults` lên `h20261009_wallet_types`. Sau nâng cấp vẫn giữ 5 user,
5 trạm, 26 trụ, 6 phiên và 6 giao dịch ví. Không khởi chạy server web trong lúc nâng.
Gate Docker cuối có báo cáo tại `outputs/sprint3-ci/20261009T134217Z-b1a94e5c/`.

Pytest local dùng Python 3.14.2; container dùng Python 3.11. Kết quả kiểm thử
tự động không thay thế review, kiểm thử thủ công và CI trên PR.

## Các phần chưa đủ bằng chứng nghiệm thu

- 5 ca SCRUM-65 còn skip: 4 ca phí chiếm trụ chờ adapter kiểm thử và 1 ca đổi phiên
  bản biểu giá khi qua ngày. Hàm tính tiền chọn phiên bản biểu giá tại lúc bắt đầu.
- Template tariffs của VY-TU có code mock, chưa có route sử dụng; form biểu giá
  thật hiện ở trang sửa trạm và chỉ cấu hình một đơn giá điện cho toàn ngày.
- Backend sandbox có API tạo/simulate-pay; trang checkout và luồng nút ví frontend
  chưa hoàn chỉnh, webhook chưa xác thực signature. Chưa nghiệm thu AC cổng/chữ ký.
- SimpleSimulator gửi Start/Stop thật nhưng chưa tự gửi số đo định kỳ trong phiên
  remote và chưa hỗ trợ ChangeConfiguration/GetConfiguration. Ca cấu hình thành
  công hiện được test với client giả trong unit test, cần client OCPP hỗ trợ để
  nghiệm thu qua mạng.
- Hướng dẫn thủ công được chuẩn bị; người dùng chưa xác nhận kết quả từng ca web.

## Bàn giao và PR

Làm lần lượt theo [hướng dẫn kiểm thử](../huongdan/kiem_thu_sau_gop_tat_ca_nhanh.md).
Nhánh tổng hợp được chuẩn bị ở local; người dùng tự push và tạo PR sau kiểm thử.
PR chọn base=`main`, compare=`codex/integration-all-branches-20261009`.
Khi nhập PR chọn **Create a merge commit**, giữ nguyên SHA/tác giả; không squash
hoặc rebase. Các phần thiếu bằng chứng ở trên cần được ghi trong mô tả/review PR.
