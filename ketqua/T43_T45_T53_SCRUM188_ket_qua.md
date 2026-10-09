# T-43, T-45, T-53 và SCRUM-188 — kết quả kiểm tra local

Ngày: **09/10/2026**, múi giờ UTC+7. Nhánh làm việc: `sprint-3`.
Đã triển khai và kiểm tra local. Báo cáo ghi nhận bằng chứng trước khi commit;
trạng thái CI/CD sau khi push xem tại GitHub Actions của commit trên `sprint-3`.

## Phạm vi hoàn thành

| Task | Kết quả |
| --- | --- |
| T-43 / SCRUM-168 | Test WebSocket thật gửi mới → cũ → trùng: chỉ một số đo trong DB, đúng một cảnh báo cho số đo cũ. Test này nằm trong pytest tự phát hiện của CI. |
| T-45 / SCRUM-170 | Stop muộn khớp phiên bằng transactionId và trụ, giữ thời gian thiết bị, chốt đúng kWh từ Wh. transactionData dùng chung bộ lọc MeterValues; gửi lại không nhân đôi số đo/hóa đơn/sổ cái. Xoá lý do chờ đối chiếu do Available sau reconnect khi đã đóng hợp lệ. |
| T-53 / SCRUM-174 | UPDATE có điều kiện chỉ đánh dấu phiên active chưa kết thúc. Ngưỡng offline mặc định 6 giờ; lệnh dừng mặc định 120 giây. Hai điều kiện cùng đúng chỉ xử lý một lần, giữ remote_stop_timeout. Job chạy lại không phát thông báo trùng, không tự chốt ended_at/kWh. |
| SCRUM-188 | JSON ba phiên tính tay thường / lùi / bằng nhau, dùng chung bởi test hàm kWh và StopTransaction, gồm cả trạng thái trước Stop active/anomaly/needs_review. |

Danh sách phiên bất thường đã nối API thật thay cho dữ liệu mẫu để hiển thị
các phiên do T-53 đánh dấu và bỏ phiên đã đóng khỏi danh sách.

Hai ca kiểm tiền có đáp án độc lập: 1.000 kWh × 1.000 đồng/kWh = 1.000 đồng;
qua hai khung giá, 0.200 kWh × 1.000 đồng + 0.800 kWh × 2.000 đồng = 1.800 đồng.
Stop dùng số đo đã lưu trong DB, gồm cả số đo trước mất mạng, để lọc bản gửi
trùng mà vẫn giữ đúng mốc tính tiền.

## Bằng chứng kiểm tra

| Bộ kiểm tra | Kết quả |
| --- | --- |
| Toàn bộ pytest theo bước CI, tách kịch bản Docker 20 trụ | **526/526 đạt**, 0 lỗi, 0 bỏ qua; khoảng 80 giây |
| JavaScript, chạy API client và script thật bằng VM/DOM doubles | **81/81 đạt** |
| Ruff | Đạt |
| Mypy | Đạt, 48 file nguồn |
| pip_audit local | Không phát hiện lỗ hổng đã biết |
| Build image Docker Python 3.11 | Đạt |
| PostgreSQL + WebSocket + job thật + API bất thường + Stop muộn | Đạt; đúng một phiên, 12.345 kWh, đúng ba số đo, replay không thay kết quả |
| Kịch bản 20 trụ, mỗi trụ ngắt–nối 1–3 lần | Cả ba lần đạt 20/20 phiên; không mất/trùng phiên hoặc số đo |

Kết quả đối chiếu từ image cuối cùng:

| Seed | Phiên khớp | kWh hệ thống | kWh simulator | Chênh lệch |
| --- | ---: | ---: | ---: | ---: |
| 42 | 20/20 | 201.060 | 201.060 | 0.000 |
| 43 | 20/20 | 201.044 | 201.044 | 0.000 |
| 44 | 20/20 | 199.915 | 199.915 | 0.000 |

Image được build từ working tree cuối cùng: `csms-app:vinh-20261009`, digest
`sha256:63bf17d9eb3a19e292a404750315c483371269649738d72af6c3302cddd6b183`.
Git SHA trong manifest là commit nền `5f7465f`, không phải commit của thay đổi
ở thời điểm kiểm tra local. Runner ba lần hoàn tất trong 35,61 giây.

Log/báo cáo runtime local (được Git ignore):

- `outputs/sprint3-ci/vinh-local.xml`
- `outputs/sprint3-ci/vinh-postgres.xml`
- `outputs/sprint3-ci/vinh-fleet-final-20261009/20261008T183943Z-b9aaf8f1/manifest.json`
- Cùng thư mục manifest có `run-1`, `run-2`, `run-3`: scenario JSON, junit và log.

Tên thư mục runtime dùng UTC; ngày báo cáo dùng UTC+7. Các phép thử mạng và
Docker dùng DB riêng; không thay dữ liệu ứng dụng local của người dùng.

## Các file triển khai chính

- `backend/app/ocpp/handlers/meter_values.py`: hàm lưu/lọc số đo dùng chung.
- `backend/app/ocpp/handlers/stop_transaction.py`: Stop muộn và dữ liệu tính tiền đã lưu.
- `backend/app/services/ocpp_handlers.py`: khoá giao dịch SQLite và chuyển số đo dồn qua bộ lọc.
- `backend/app/services/jobs.py`: job có điều kiện, thông báo sau commit.
- `backend/tests/scrum188_sessions.json`, `backend/tests/conftest.py`: bộ mẫu và fixture.
- `backend/tests/unit/test_session_energy.py`, `test_stop_transaction.py`, `test_session_review_jobs.py`: kiểm tra hàm/handler/job.
- `tests/test_sprint2_network.py`: T-43, T-45/T-53 qua server/WebSocket thật.
- `tests/sprint2_docker_acceptance.py`: kiểm tra PostgreSQL được bước CI Docker hiện có thu thập.
- `frontend/static/js/api_client.js`, `tests/frontend_behavior.cjs`: danh sách bất thường lấy dữ liệu thật.
- `.env.example`, `README.md`, `docker-compose.acceptance.yml`: cấu hình và mô tả hành vi.

Hướng dẫn chạy lại: [kiem_thu_T43_T45_T53_SCRUM188.md](../huongdan/kiem_thu_T43_T45_T53_SCRUM188.md).

## Phần nghiệm thu còn cần team thực hiện

Các bằng chứng ở trên là kết quả local; GitHub Actions kiểm tra lại khi push.
Chưa triển khai/kiểm thử trên staging, chưa có review của thành viên khác. Theo bảng phân
công: Tân review T-43/T-53/SCRUM-188, Lâm Tùng review T-45. Báo cáo không thay
cho các bước nghiệm thu này.
