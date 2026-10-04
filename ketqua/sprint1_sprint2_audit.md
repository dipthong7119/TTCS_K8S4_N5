# Đối chiếu Sprint 1 và Sprint 2: Excel → code

Ngày kiểm tra: 04/10/2026. Nhánh `main` local và GitHub hiện ở `255bd32`, đã chứa các bản sửa Sprint 1–2, dọn file và commit hợp nhất `baf6256`. Bản sửa dependency cho lỗi audit CI/CD của lượt kiểm tra lại đang ở working tree.

## Kết luận

**Phần chức năng Sprint 1–2 đã được hoàn thiện và đạt các kiểm thử tự động trên máy này; chưa đủ bằng chứng để xác nhận hoàn tất toàn bộ tiêu chí nghiệm thu trong Excel gốc.** Đối chiếu theo nội dung 35 task/17 backlog, bỏ qua cột trạng thái như người dùng yêu cầu. Hai lỗi của dữ liệu mẫu đã được sửa. Sau dọn file dư và đồng bộ main mới, 296 test Python và 25 test JS đạt; vẫn giữ test hợp đồng health trong `tests/test_health.py`, bộ Heartbeat mới tăng thêm sáu bài so với lần kiểm tra sau dọn file. Kết quả Docker và nghiệm thu xem phần bằng chứng bên dưới. CI trên GitHub, staging, duyệt code bởi thành viên khác và nghiệm thu giao diện trực quan vẫn cần bằng chứng trên đúng môi trường.

Nguồn đối chiếu là workbook **Nền tảng vận hành trạm sạc xe điện (CSMS).xlsx**, các sheet `Tasks`, `Backlog`, `DoD-DoR`; lọc theo cột `Sprint` bằng 1 hoặc 2, không lấy một khoảng dòng liên tiếp. Các task Sprint 3 xen giữa trong sheet đã được loại khỏi phạm vi.

- **35 task:** T-01–T-35. Trạng thái Excel: 6 Done, 3 In Progress, 26 Todo.
- **17 backlog:** S-01–S-16 và K-01. Trạng thái Excel: 4 Done, 1 In Progress, 12 Todo.
- Trạng thái Excel chưa phản ánh đầy đủ code hiện có: nhiều dòng Todo đã có implementation và test. Ngược lại, một số dòng Done vẫn có lỗi so với AC.
- Workbook đã có thay đổi khi bắt đầu kiểm tra. Lượt này chỉ đọc workbook, không sửa hay tự chuyển các dòng sang Done.

“Đạt local” trong báo cáo có nghĩa là phần được kiểm tra bằng code/test trên máy này đạt yêu cầu tương ứng; không thay thế nghiệm thu staging hay toàn bộ DoD.

## Đánh giá theo phạm vi web dùng dữ liệu giả lập

Người dùng xác nhận dự án chỉ là web, không có phần cứng gửi request; dữ liệu giả dùng để kiểm thử chức năng. Phạm vi này phù hợp với đặc tả: mọi trụ là phần mềm trong `dev_tools/ocpp_simulator/`. Không cần mua hay kết nối trụ vật lý để hoàn thành Sprint 1–2. `vendor`, `model`, `firmwareVersion` là trường dữ liệu giả của giao thức, không phải yêu cầu phát triển firmware.

- **Kế hoạch đủ cho mục tiêu hai sprint:** Sprint 1 có 6 backlog/11 task cho hạ tầng, tài khoản, quyền, trạm, trụ và spike simulator; Sprint 2 có 11 backlog/24 task cho kết nối, xử lý bản tin, heartbeat, trạng thái, theo dõi, mất kết nối, chống xử lý trùng, Authorize và Reset. Phiên sạc, tính tiền và các chức năng các sprint sau không phải hạng mục thiếu của Sprint 1–2.
- **Kiểm thử chức năng bằng dữ liệu giả:** phần mềm simulator gửi payload giả qua WebSocket tới backend, backend lưu DB và đẩy SSE tới web. Đây là luồng đã được bộ kiểm thử mạng/Docker kiểm chứng. Dữ liệu giả vẫn phải đi qua luồng này để kiểm được xử lý bản tin và Reset; chỉ đổi dữ liệu trong JavaScript không đủ chứng minh backend đúng.
- **Hai lỗi của chế độ “20 trụ mẫu” đã được sửa theo yêu cầu bổ sung:** `RealtimeStatus` nhận đúng danh sách trụ/đầu nối từ grid, nên sự kiện khớp cả 20 trụ. Reset mẫu trả Accepted, chuyển offline/unknown và phục hồi online/Available sau 2 giây, qua bộ mô phỏng trên trình duyệt. Dữ liệu máy chủ vẫn gửi Reset qua API. Refresh giữ trạng thái mô phỏng; đổi nguồn dừng timer và ngăn xác nhận cũ gửi lệnh sang nguồn khác. Người dùng yêu cầu giữ nguyên Excel và bỏ qua cột trạng thái khi đánh giá.
- **Nghiệm thu:** theo yêu cầu hiện tại, đánh giá trên máy này. CI GitHub, staging và review vẫn là hạng mục chưa có bằng chứng theo Excel gốc; chúng không liên quan tới phần cứng. Khi chốt bàn giao local cần ghi rõ môi trường và các tiêu chí đã kiểm, không tự coi AC trên staging đã chạy.

Riêng đợt sửa hai điểm bổ sung đạt **25 test JavaScript** và **2 test mạng backend** (SSE và Reset). Đợt kiểm tra chốt sau đó đã chạy lại toàn bộ Python, JS và Docker như phần bằng chứng bên dưới. Workbook giữ nguyên; SHA256 vẫn là `C106E9B5E8458F2F02EF00604BDDED75882E9CFAF4D60C32EECCF2837471BA30`.

## Những lỗi đã sửa

1. **T-01/T-04/T-08/T-10:** Alembic có hai head làm `upgrade head` không chạy được. Thêm merge revision và sửa downgrade của các migration kiểm tra cột đã tồn tại, để không xoá cột thuộc migration trước. Kiểm thử nâng schema và hạ về `base` chạy thật trên DB tạm.
2. **S-04/S-05:** Trạm mới trước đây mặc định `active`, connector mới mặc định `unavailable`, trái AC trong Backlog. Đồng bộ schema, model và API về `inactive`/`unknown`; có migration mới cho database đã tồn tại.
3. **T-06/S-03:** Guard từ chối route chưa khai quyền trước đây chỉ áp dụng ở một số router. Gắn guard ở cấp ứng dụng, khai báo rõ các trang public và các trang có quyền. Route mới chưa khai quyền trả 403 ngay cả với admin; OCPP vẫn đi qua kiểm tra mã trụ/subprotocol riêng.
4. **T-08:** Bật kiểm tra foreign key trên engine SQLite của ứng dụng. Có test chứng minh DB chặn xoá chủ trạm khi vẫn còn trạm.
5. **S-05:** API sửa mã trụ trước đây không thực hiện đầy đủ quy tắc khi trụ đã có phiên sạc. Bổ sung kiểm tra mã unique và chặn sửa mã khi đã có phiên; chặn xoá trụ còn phiên đang mở.
6. **T-09/S-04:** Sau khi API lưu thành công, nút Lưu có thể bật lại trong thời gian chờ chuyển trang. Bổ sung tuỳ chọn giữ nút disabled sau thành công; lỗi vẫn cho phép thử lại.
7. **T-15:** Khung JSON `[]` gây `IndexError` và làm đóng WebSocket. Trả `FormationViolation`, giữ kết nối và tiếp tục nhận Heartbeat.
8. **T-17/T-26:** Hai cấu hình khoảng Heartbeat có thể khác nhau giữa Boot và phát hiện offline. Dùng một giá trị chuẩn `OCPP_HEARTBEAT_INTERVAL_SECONDS`, vẫn nhận tên cũ `HEARTBEAT_INTERVAL`. Boot bị Rejected chuyển trụ về offline và connector về unknown.
9. **T-18:** UPDATE ORM tự thêm `updated_at` do `onupdate`, trái yêu cầu cập nhật đúng một cột. Thay bằng câu lệnh có bind parameter chỉ ghi `last_seen_at = CURRENT_TIMESTAMP`; test kiểm tra SQL thực tế và việc giữ nguyên `updated_at`. Khung sai và tin trước Boot cũng ghi nhận thời điểm liên lạc, nhưng không chuyển trụ sang online.
10. **T-20/T-21:** `connectorId=0` trước đây không lưu trạng thái cả trụ; `error_code` hiện tại của connector chưa được đồng bộ. Sửa cả hai; khôi phục `NoError` giữ nguyên lịch sử lỗi. Chuẩn hoá timestamp không có timezone theo UTC.
11. **T-21:** Migration đổi `timestamp` sang `occurred_at` có thể thay giờ lỗi cũ bằng giờ migrate. Sao chép thời gian cũ trước khi bỏ cột, cả chiều upgrade/downgrade; có test bảo toàn thời điểm lịch sử.
12. **T-12/T-23/T-25:** Test 50 trụ thật phát hiện timeout Heartbeat. Phần phát snapshot SSE trước đây truy vấn connector riêng cho mỗi trụ trên mỗi bản tin. Bỏ truy vấn khi không có subscriber và dùng một truy vấn join khi cần snapshot, đồng thời dùng serializer suy trạng thái stale giống API tree.
13. **T-26/S-12:** Trụ quay lại trước khi job offline chạy có thể giữ trạng thái connector cũ. Xoá trạng thái cũ về unknown trước khi xử lý bản tin mới nếu quá hạn hoặc đang offline.
14. **T-03:** Workflow cũ thay container trước khi kiểm tra rồi mới rollback. Kiểm tra image mới trên cổng loopback trước khi thay; kiểm cả `/health` và trang chủ; thêm nhánh phục hồi image trước đó và tránh hai deploy chạy đồng thời. Tách mount frontend local sang `docker-compose.override.yml` để staging dùng frontend nằm trong image mới.
15. **T-01/S-01:** Dùng `.env.example` nguyên bản có thể làm Settings lỗi vì trường backup chưa được khai báo. Thêm trường tương ứng và test nạp cấu hình mẫu.
16. **Test/README:** Sửa assertion sai của Authorize, thay test migration mô phỏng bằng migration thật, sửa fixture thiếu và việc test job dùng DB ứng dụng. Test WebSocket trả lại cấu hình SessionLocal sau mỗi test. Bỏ dấu merge conflict trong README và chuyển JS nghiệp vụ inline của login/layout sang file JS riêng.
17. **T-02/DoD:** Bổ sung Mypy và pip-audit ở cả CI và bước kiểm tra trước deploy; thêm cấu hình kiểu và annotation cần thiết. Typecheck kiểm cả thân hàm chưa có annotation, còn model ORM legacy là ranh giới động. Quét phát hiện pip cũ có lỗ hổng; nâng pip trong `.venv`, CI và Docker build, quét lại sạch. Annotation của các biến gom dữ liệu giá chỉ đổi thông tin kiểu, không đổi công thức tính tiền.
18. **T-01/T-21:** Chạy PostgreSQL thật phát hiện mã revision `h20261003_t21_ocpp_request_payload` dài hơn `VARCHAR(32)` của Alembic, làm container không khởi động. Migration mở rộng cột phiên bản trước khi ghi mã này; giữ nguyên ID đã dùng trên SQLite. PostgreSQL upgrade, downgrade tới base và bảo toàn lịch sử lỗi đều qua.
19. **T-01:** Sau migration, script seed còn truyền `info`/`timestamp` đã bị loại khỏi model `ConnectorError`, khiến startup development/Compose thất bại. Sửa về `occurred_at`; kiểm seed hai lần không tăng số bản ghi trên SQLite và PostgreSQL.
20. **T-02:** CI trước đây build bằng Buildx rồi Compose build lại. Nạp image từ Buildx và dùng `--no-build`; tách công cụ kiểm tra sang `requirements-dev.txt` để image ứng dụng chỉ cài runtime. Thêm báo cáo coverage XML và kiểm thử hành vi JS trong CI; JS thất bại cũng chặn job deploy.
21. **T-24/T-25:** API tree rỗng hoặc lỗi trước đây tự đổi màn hình sang 20 trụ mẫu. Chỉ dùng mẫu khi người dùng chủ động chọn; lỗi giữ dữ liệu thật đã tải và thông báo rõ. Tải lại tree sau SSE reconnect, bỏ response cũ khi đổi nguồn dữ liệu có test chạy JS thật.
22. **T-35:** Hai lần bấm Reset có thể tạo waiter xác nhận bị bỏ quên hoặc gửi lệnh lặp trong lúc chờ. Chặn theo mã trụ trong suốt xác nhận/RPC; mở hộp xác nhận khác giải phóng waiter cũ, giữ nút offline disabled. Có test xác nhận, gửi lặp, huỷ/chuyển hộp và offline.
23. **T-24:** `last_seen_at` không có offset từ DB trước đây bị JavaScript hiểu là giờ địa phương. Chuẩn hoá đầu vào UTC khi hiển thị, giữ đúng instant với cả timestamp naive và timestamp có offset; có hai ca kiểm thử.
24. **T-01/T-19/T-27:** Thêm `docker-compose.acceptance.yml` dùng project riêng, cổng localhost ngẫu nhiên, PostgreSQL tạm trong RAM; thêm bộ kiểm tra Docker chạy lại được và đưa vào CI. Không dùng database/volume của ứng dụng hiện có. Sửa teardown fixture để đóng các connection/engine thử nghiệm khi chạy coverage.
25. **T-24/T-25:** Sửa lệch mã trụ giữa bộ phát sự kiện giả và grid. Mã/đầu nối lấy từ dataset đang hiển thị; cập nhật cả trạng thái OCPP, trạng thái nội bộ, giờ liên lạc cuối, tổng số và drawer. Offline xoá trạng thái đầu nối về unknown; online phát Available cho đúng các đầu nối. Nhãn “Đang mô phỏng” vẫn rõ khi SSE backend bị đứt.
26. **T-35:** Truyền bộ gửi Reset theo nguồn dữ liệu vào component. Reset mẫu có xác nhận mềm/cứng, Accepted, offline rồi online sau 2 giây; trụ offline hoặc đang restart bị chặn. Đổi nguồn huỷ timer và vô hiệu xác nhận cũ; Reset dữ liệu máy chủ vẫn dùng API. Đã kiểm cả handler và sự kiện click của nút.

## Bảng Tasks

| ID | Backlog | Excel | Kết quả đối chiếu và kiểm chứng |
|---|---|---|---|
| T-01 | S-01 | In Progress | Đạt local trên Docker/PostgreSQL: app/db healthy, migration lên head/hạ base, FK/unique và seed lặp qua. Đã sửa thêm lỗi revision quá dài và seed dùng trường cũ. |
| T-02 | S-01 | In Progress | Build/lint/typecheck/audit/Python/JS/Docker tests đạt local. CI dùng lại image đã build, xuất coverage XML. Chưa xác minh workflow GitHub <5 phút hoặc branch protection. |
| T-03 | S-01 | In Progress | Các nhánh script deploy qua test stub; thêm test Docker thật chứng minh candidate thoát lỗi 42 không thay container cũ, `/health` và trang chủ cũ vẫn 200. Chưa có staging để đo deploy <10 phút. |
| T-04 | S-02 | Done | Đạt local: migration, email unique, đúng 5 role, hash/password của tài khoản seed. |
| T-05 | S-02 | Done | Đạt local: session cookie, thông báo chung, đếm sai và khoá theo tài khoản/IP trong DB; hết hạn khoá và đăng nhập lại. JS login đã tách khỏi template. |
| T-06 | S-03 | Done | Đã sửa guard toàn ứng dụng. Test route mới chưa khai quyền trả 403 với admin qua. |
| T-07 | S-03 | Done | Đạt local: lọc query dùng chung, chủ trạm khác nhận 403 và có log; driver không vào API vận hành. |
| T-08 | S-04 | Done | FK và schema qua trên cả SQLite/PostgreSQL; chặn xoá chủ trạm còn trạm. |
| T-09 | S-04 | Done | CRUD/validation/ownership qua test API; đã sửa trạng thái mặc định và chặn lưu lần hai sau thành công. Chưa xác minh tương tác trực quan trên browser. |
| T-10 | S-05 | Todo | Đạt local: bảng, unique mã trụ toàn hệ thống, connector 1–4 và unknown, migration rollback. |
| T-11 | S-05 | Todo | Có kiểm trùng khi blur và kiểm lại ở server. API trùng/khác chủ/giới hạn connector qua; chưa thao tác form trực quan. |
| T-12 | S-06 | Todo | Đạt local cả SQLite và Docker/PostgreSQL: bài Docker giữ 50 socket + SSE 600,6 giây, 237 vòng Heartbeat, đủ 200 connector; SSE 0,047s, tree HTTP 0,040s. Chờ nghiệm thu staging. |
| T-13 | S-06 | Todo | Đạt local qua mạng thật: mã lạ bị từ chối dưới 1 giây; đúng một warning gồm mã và IP. Lý do trả trụ được đổi thành thông báo chung. |
| T-14 | S-07 | Todo | Parser/packer thuần và round-trip có test; xử lý CALL/CALLRESULT/CALLERROR không phụ thuộc WebSocket. Có tài liệu và trace K-01 làm nguồn tham chiếu. |
| T-15 | S-07 | Todo | Qua mạng thật: 5 nhóm khung sai và thêm `[]` trả đúng mã lỗi; Heartbeat tiếp theo vẫn nhận phản hồi. |
| T-16 | S-08 | Todo | Đạt local: lưu vendor/model/firmware, thiếu trường lưu NULL, Boot lần sau cập nhật trụ cũ. |
| T-17 | S-08 | Todo | Đã sửa nguồn cấu hình và trạng thái Rejected. Test locked/inactive/Accepted, UTC, interval và gate trước Boot qua; server riêng chạy interval 5 giây. |
| T-18 | S-09 | Todo | Đã sửa UPDATE một cột theo DB clock; test kiểm SQL, Heartbeat, StatusNotification và các loại phản hồi qua. |
| T-19 | S-09 | Todo | Đạt local bằng container thật `TZ=UTC-5`: client báo giờ lệch +5 tiếng, `last_seen_at` lệch DB clock 0,494 giây (<2 giây). Bộ này đã được nối vào CI. |
| T-20 | S-10 | Todo | Đạt local: 9 trạng thái, raw status lạ, connectorId=0, cập nhật error_code. SSE qua mạng nhận Charging dưới 1 giây. |
| T-21 | S-10 | Todo | Đạt local: lịch sử lỗi append, phục hồi không xoá lịch sử, vendor error/timestamp/index. Đã sửa bảo toàn thời gian lỗi khi migrate. |
| T-22 | S-10 | Todo | Đạt local: connector chưa khai báo không được tạo, phản hồi rỗng, warning có throttle. |
| T-23 | S-11 | Todo | Test 50 trụ/200 connector: cây đúng, một query, <200ms trên DB test, lọc ownership. Đã dùng cùng cách join cho snapshot SSE. |
| T-24 | S-11 | Todo | Đã sửa dữ liệu mẫu tự xuất hiện, giờ liên lạc cuối và cập nhật đúng 20 trụ mẫu/grid/tổng số/drawer. JS kiểm nguồn dữ liệu/UTC; có grid responsive, nhãn chữ/màu. Chưa đo render/scroll ngang bằng browser. |
| T-25 | S-11 | Todo | SSE trên PostgreSQL với 50 socket đạt <1 giây. Test JS kiểm tree reload sau reconnect, update connector và không đóng EventSource khi lỗi; bộ phát mẫu lấy đúng mã/đầu nối từ grid. Chưa nghiệm thu restart bằng trình duyệt thật. |
| T-26 | S-12 | Todo | Job dùng DB cutoff và chạy lại no-op qua. Qua server thật: giữ socket nhưng ngừng bản tin, quá hai chu kỳ bị offline/unknown, Heartbeat phục hồi online và chờ status mới. Tree suy stale khi job chưa chạy có test. |
| T-27 | S-12 | Todo | Ba vòng dừng/bật container simulator thật trên PostgreSQL qua; kiểm sau >2 chu kỳ 5 giây là offline/unknown, bật lại là online/rảnh. Chưa chạy trên staging vì chưa có môi trường đó. |
| T-28 | S-13 | Todo | Đạt local: một kết nối sống cho mỗi mã; thay socket cũ; pending call gắn với đúng socket. README ghi giới hạn một process. |
| T-29 | S-13 | Todo | Qua mạng thật: kết nối cũ nhận đóng, kết nối mới tiếp tục xử lý. Test unit kiểm tránh gửi phản hồi của socket cũ sang socket mới qua. |
| T-30 | S-14 | Todo | Đạt local: khoá unique theo mã trụ/msg_id, lưu request/response trong transaction, gửi lặp không chạy lại handler, cảnh báo khi cùng mã khác nội dung. |
| T-31 | S-14 | Todo | Cleanup 7 ngày, biên và no-op qua. Gửi lặp 5 lần nhận đúng response; restart process server thật rồi gửi lại vẫn nhận response lưu và chỉ một bản ghi. |
| T-32 | S-15 | Todo | Đạt local: id_tags unique, khoá/hạn dùng/FK và thẻ demo gắn driver. |
| T-33 | S-15 | Todo | Qua mạng thật: Accepted, Blocked, Expired, Invalid và trạm inactive bị Blocked. Test log chỉ giữ 4 ký tự cuối qua; assertion parser đã sửa. |
| T-34 | S-16 | Todo | Qua mạng thật: CALL Reset, khớp response theo ID, bỏ response không khớp, HTTP khác không bị chặn, timeout huỷ chờ. Unit có nhánh CALLERROR/socket cũ. |
| T-35 | S-16 | Todo | API/role/offline/timeout/audit qua. JS kiểm xác nhận Reset, chặn lệnh lặp, giải phóng hộp cũ, offline và Reset mẫu mềm/cứng phục hồi sau 2 giây; đổi nguồn huỷ mô phỏng và chặn xác nhận cũ. Chưa thao tác trực quan bằng browser. |

## Bảng Backlog

| ID | Sprint | Excel | Kết quả tổng hợp |
|---|---|---|---|
| S-01 | 1 | In Progress | Docker/PostgreSQL local đã chạy thật sau sửa migration và seed; candidate lỗi giữ app cũ. Chờ CI GitHub/staging. |
| S-02 | 1 | Done | Login/session/lockout/role seed đạt local; chờ nghiệm thu giao diện và DoD chung. |
| S-03 | 1 | Done | Đã sửa default deny toàn app; ownership và role checks đạt local. |
| S-04 | 1 | Done | Đã sửa inactive mặc định và chặn double submit sau thành công. CRUD, FK và validation đạt local; chờ browser/staging. |
| S-05 | 1 | Todo | Đã sửa connector unknown và quy tắc đổi mã trụ sau phiên. Unique/connector count/API đạt local; chờ browser/staging. |
| K-01 | 1 | Done | Repo có tài liệu chọn simulator, trường dữ liệu của 8 action và trace 26 frame. Đã kiểm tra chứng cứ có sẵn; không chạy lại spike từ nguồn bên ngoài trong lượt này. |
| S-06 | 2 | Todo | Admission/WS đạt local; 50 kết nối 10 phút đạt trên cả SQLite và Docker/PostgreSQL, bài PostgreSQL có SSE subscriber hoạt động đồng thời. Chờ staging. |
| S-07 | 2 | Todo | Parser/packer và khung lỗi đạt local, gồm trường hợp mảng rỗng đã sửa; remote response correlation đạt local. |
| S-08 | 2 | Todo | Boot fields, UTC, Accepted/Rejected, gate và interval đạt local sau sửa. |
| S-09 | 2 | Todo | DB clock/UPDATE một cột và container trụ lệch +5 tiếng đều đạt local trên PostgreSQL. |
| S-10 | 2 | Todo | Mapping, raw status, connector 0, lỗi append và connector lạ đạt local sau sửa. |
| S-11 | 2 | Todo | Tree/SSE đạt local; sửa nguồn dữ liệu và hiển thị UTC, JS kiểm reconnect/update. Chờ browser đo layout/render/restart trực quan. |
| S-12 | 2 | Todo | Offline cutoff/no-op/stale/recovery đạt local; ba vòng container thật trên PostgreSQL qua. Chờ staging. |
| S-13 | 2 | Todo | Duplicate socket, đóng socket cũ và tránh nhầm phản hồi đạt local. |
| S-14 | 2 | Todo | DB idempotency/cleanup/5 lần gửi lại/restart process đạt local. |
| S-15 | 2 | Todo | Unique tag và các nhánh Authorize đạt local, có test qua mạng thật và masking log. |
| S-16 | 2 | Todo | Reset API và hành vi JS đạt local, gồm xác nhận/chặn lặp/đổi hộp. Chờ nghiệm thu trực quan và staging. |

## Bằng chứng kiểm thử

- Bộ Python sau đồng bộ main mới: **296 passed, 47 warnings**, **52,25 giây**, có coverage, Python **3.14.2** trên Windows, không skipped. Bộ Heartbeat mới có 10 bài đạt. Bỏ `test_placeholder.py` trùng bài health đã có trong `tests/test_health.py`; coverage tổng vẫn 62%, riêng handler Heartbeat đạt 100%. App và simulator Docker chạy **Python 3.11**. Workflow GitHub tại `255bd32` đã chạy nhưng dừng ở audit; kết quả kiểm tra lại trên Linux xem phần CI/CD bên dưới.
- Bộ Docker sau dọn file dư: **5 passed**, **75,44 giây**; bên trong có **10 migration/seed tests trên PostgreSQL** qua trong 11,39 giây, đồng hồ trụ lệch +5h nhưng delta DB 0,509s, 50 socket + SSE smoke (latency 0,031s; tree HTTP 0,031s), ba vòng container stop/start, candidate lỗi giữ app cũ. Bài soak 600 giây trên Docker/PostgreSQL đã chạy riêng trong đợt kiểm thử trước; không chạy lại sau dọn file vì không đổi nghiệp vụ backend.
- Node sau sửa chế độ mẫu: **25 tests passed**, thực thi JS của form/monitoring/Reset/SSE trong DOM/EventSource doubles, gồm 20 mã trụ/đầu nối, grid/drawer/tổng số, Reset mẫu Soft/Hard, offline, refresh, đổi nguồn, chặn lệnh trùng và click dùng đúng bộ gửi lệnh. Các test này không đo kích thước/layout/render trình duyệt.
- Kiểm hồi quy mạng sau sửa frontend: **2 passed, 7 deselected, 1 warning**, **6,81 giây**; SSE đẩy thay đổi đầu nối dưới 1 giây và Reset qua HTTP/WebSocket vẫn khớp response, không chặn request khác, xử lý timeout/audit đúng.
- Coverage bỏ code test khỏi mẫu số: **62% tính cả dòng và nhánh** của `app` (gồm cả module ngoài Sprint 1–2). Có `backend/coverage.xml` và CI upload artifact; chưa có baseline cùng điều kiện để kết luận độ phủ phần thay đổi không giảm. Server subprocess/Docker không được cộng vào báo cáo coverage này.
- Ruff: **All checks passed**, phạm vi `app`, `alembic`, `../tests`.
- Mypy: **Success: no issues found in 41 source files**, kiểm cả thân hàm chưa có annotation. Cấu hình bỏ qua model `Column`/`declarative_base` legacy, test và simulator; không có tuyên bố toàn bộ ORM đã được kiểm kiểu chặt.
- pip-audit trên `.venv` và danh sách package/version thực tế trong image runtime: **No known vulnerabilities found**. Công cụ dev được ghi trong `requirements-dev.txt`; image chỉ dùng `requirements.txt`.
- `node --check`: toàn bộ file JS trong `frontend/static/js` qua.
- Soak riêng T-12: **50 socket OCPP**, **600,7 giây**, **240 vòng Heartbeat**, API tree xác nhận **50 online / 200 connector**. Tổng bài soak 607,09 giây. Không có browser SSE subscriber trong bài soak dài; tải SSE được kiểm tra riêng và snapshot được kiểm tra số query riêng.
- Soak Docker/PostgreSQL T-12/T-25: **50 socket + một subscriber SSE HTTP**, **600,6 giây**, **237 vòng Heartbeat**, **200 connector**, **SSE 0,047 giây**, **tree HTTP 0,040 giây**. Bài test qua trong **605,35 giây**. Subscriber này là HTTP client độc lập, không phải browser. Soak kiểm backend; bản chỉnh format giờ ở frontend được kiểm riêng bằng Node và build image cuối.
- HTTP/WebSocket độc lập: admission <1 giây, khung lỗi không ngắt kết nối, duplicate socket, reconnect 3 lần, Authorize, SSE <1 giây, Reset, timeout, offline deadline và restart process.
- Deploy: script workflow qua năm nhánh stub; thêm test Docker thật candidate thoát 42 giữ nguyên container đang chạy. Chưa truy cập staging hoặc thử promotion/rollback thật trên server staging.
- YAML của Compose/workflow được đọc bởi test deploy; staging không mount frontend cũ, override local giữ mount.
- Image cuối đã build lại với frontend sửa giờ UTC; startup `/health`, trang chủ và hai file JS monitoring/Reset đều qua HTTP check. Bộ container/network nghiệm thu đã được dọn; hai container ứng dụng có sẵn vẫn giữ trạng thái dừng ban đầu.
- Lần chốt đã build lại image với hai bản sửa chế độ mẫu; app/db healthy. Ba file JS realtime/Reset/monitoring được lấy qua HTTP đều trả 200 và nội dung trùng file workspace. Project Docker nghiệm thu riêng là `csms-sprint12-final-check`, được dọn sau kiểm thử; không dùng dữ liệu ứng dụng có sẵn.
- Migration tests dùng database tạm. Test job cleanup trong pytest đã chuyển sang fixture DB riêng; server mạng dùng DB tạm riêng và dừng sau test.
- Warnings gồm deprecation từ TestClient/Alembic và ResourceWarning của một số fixture legacy trên Python 3.14; không phải test thất bại. Các fixture chính và connection mạng đã được bổ sung teardown.

Chạy lại từ PowerShell tại thư mục repo:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m ruff check app alembic ../tests
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pip_audit --local --progress-spinner off
..\.venv\Scripts\python.exe -m pytest app/tests ../tests --tb=short -q
..\.venv\Scripts\python.exe -m pytest ../tests/test_sprint2_network.py::test_50_real_connections_with_heartbeat_and_200_connectors --sprint2-soak-seconds=600 -q -s
Pop-Location
node --test tests/frontend_behavior.cjs
docker compose --env-file .env.example -p csms-sprint12-acceptance -f docker-compose.acceptance.yml up -d --build --wait db app
.\.venv\Scripts\python.exe -m pytest tests/sprint2_docker_acceptance.py -v -s
.\.venv\Scripts\python.exe -m pytest tests/sprint2_docker_acceptance.py -k 50_connections --sprint2-soak-seconds=600 -v -s
docker compose --env-file .env.example -p csms-sprint12-acceptance -f docker-compose.acceptance.yml down -v --remove-orphans
```

Mặc định bài soak trong bộ test chỉ giữ ngắn để phù hợp CI; cần truyền `--sprint2-soak-seconds=600` để nghiệm thu thời lượng 10 phút.

## Dọn file trước khi đưa lên GitHub

Đã đưa **1.682 file dư, 17.146.404 byte (khoảng 17 MB)** ra khỏi thư mục dự án. Các file có bản lưu phục hồi bên ngoài repo tại `E:\TTCS_K8S4_N5_cleanup_backup_20261004_230c9050`; danh sách nằm trong `cleanup_manifest.json` của thư mục đó.

- Bỏ bản sao công cụ AI `backend/skillbackend/` (229 file) và `frontend/skillfrontend/` (1.434 file); không có import hoặc tham chiếu từ runtime/CI.
- Bỏ `prompts/ke_hoach_sprint2.zip` và thư mục giải nén 12 file; giữ tài liệu `.docx` gốc. SHA256 của ZIP và DOCX trùng nhau.
- Bỏ bốn file xử lý/kết quả dùng một lần ở root: `patch_a6d2f891c104.py`, `read_excel.py`, `generate_summary.py`, `baseline_test_results.txt`; bỏ prompt Sprint 2 cũ chứa hướng dẫn mặc định trái đặc tả hiện tại.
- Bỏ `backend/app/tests/unit/test_placeholder.py` trùng test hợp đồng health đã có trong `tests/test_health.py`. Sau dọn, **290 Python tests** vẫn đạt; coverage tổng giữ 62%.
- Hai file `.env` được bỏ theo dõi Git và giữ nguyên trên máy. `.env.example` vẫn được theo dõi. Bổ sung ignore cho env cục bộ, cache, coverage và các bản sao công cụ AI; Docker context loại tài liệu, test và dữ liệu cục bộ khỏi image runtime.
- Docker build và app/db healthy; simulator vẫn có trong image, các file JS/CSS chính trả HTTP 200. Khi chạy lại, kịch bản bật simulator đã khiến Compose dựng lại DB tmpfs; sửa kịch bản dùng `--no-deps` và kiểm ID app/db không đổi trong cả ba vòng. Bộ Docker sau sửa đạt **5/5**.
- Workbook, migration, mã nghiệp vụ, simulator, bộ kiểm thử dùng lại và tài liệu gốc được giữ. SHA256 workbook vẫn là `C106E9B5E8458F2F02EF00604BDDED75882E9CFAF4D60C32EECCF2837471BA30`.

## Đồng bộ main sau cập nhật của thành viên

- Đã fetch/pull commit `65d0b2f` (Scrum 45). Remote main bị force-update từ `ccc3a5d` về một nhánh bắt đầu tại `0d4a1ca`; dùng merge commit local `baf6256` để giữ các commit kiểm thử/sửa lỗi của nhóm và tích hợp thay đổi Heartbeat mới. Không reset về remote và chưa push lên GitHub.
- Xung đột duy nhất khi pull nằm trong `nhat_ky.md`: giữ các dòng nhật ký của cả hai phía, bỏ marker và dòng trùng. Toàn bộ bản sửa Sprint 1–2, hai lỗi chế độ mẫu, 1.682 file đã dọn và trạng thái bỏ theo dõi hai file `.env` được khôi phục sau merge.
- Bản sao trước đồng bộ tại `E:\TTCS_K8S4_N5_sync_backup_20261004_225956`: có 72 file đang làm/cấu hình, patch working tree/index, Git history bundle, manifest SHA256 và mã stash phục hồi. Giữ stash để có thể phục hồi; không thêm bản sao vào dự án.
- Bộ Heartbeat mới có lỗi lint và test đếm UPDATE từ biểu diễn SQLAlchemy chưa biên dịch, gây báo ba lần dù SQL thực tế chỉ ghi `last_seen_at` một lần. Sửa listener để kiểm SQL thực tế và đúng cột SET. Sửa bài migration dùng database tạm qua `settings.DATABASE_URL`, không skip do sai đường dẫn, và giữ cột `last_seen_at` thuộc migration trước khi downgrade. Gate BootNotification vẫn được kiểm ở tầng WebSocket; test handler offline được mô tả đúng phạm vi.
- Sau hợp nhất: **296 Python tests** đạt trong **52,25 giây**, **25 JS tests** đạt, Ruff và Mypy đạt (41 source files). Docker image dựng lại thành công; **5 Docker tests** đạt trong **73,28 giây**, gồm **10 migration/seed tests PostgreSQL**, đồng hồ trụ lệch +5 giờ (DB delta **0,538 giây**), 50 socket/200 connector/SSE, ba vòng dừng/bật simulator và candidate lỗi giữ ứng dụng cũ healthy. SSE **0,030 giây**, API tree **0,041 giây** trong bài smoke.
- Project Docker kiểm tra riêng là `csms-main-sync-check`, được dọn sau kiểm thử. Workbook vẫn cùng SHA256 đã ghi; `backend/csms.db` và hai file cấu hình local giữ nguyên nội dung. Không chỉnh trạng thái Todo trong Excel.

## Kiểm tra lại CI/CD GitHub (T-02/T-03)

- Đã đọc trạng thái job và log thật của commit `255bd32`: [CI Pipeline](https://github.com/dipthong7119/TTCS_K8S4_N5/actions/runs/37216225199/job/111477169097) và [CD Pipeline](https://github.com/dipthong7119/TTCS_K8S4_N5/actions/runs/37216225255/job/111477169229). Cả hai qua cài dependency, Ruff và Mypy, rồi fail tại **Audit installed dependencies**; pytest và các bước sau bị skip. Job deploy-staging chưa chạy.
- Log audit chỉ ra `setuptools 79.0.1`, `PYSEC-2026-3447` (hai mục cùng ID cho một package), bản sửa từ `83.0.0`. Bản cũ có sẵn trên Python 3.11 của runner và image Docker; môi trường Windows Python 3.14 kiểm tra trước đó không tái hiện lỗi này.
- Thêm `setuptools>=83.0.0` vào `backend/requirements.txt`. Cả CI và CD dùng `requirements-dev.txt` bao gồm file này; Docker cũng cài file này, nên một ràng buộc chung nâng đúng package ở cả ba môi trường. Giữ bước audit để chặn dependency có lỗ hổng.
- Đã tái hiện audit thất bại với `79.0.1` trên Linux/Python **3.11.16**, rồi nâng bằng requirements đã sửa lên **84.0.0**. Sau sửa: audit không có lỗ hổng đã biết, Ruff qua, Mypy qua **41 source files**, **296 Python tests** qua trong **56,83 giây**, không skipped (coverage tổng trên Python 3.11 là **63%**). **25 JS tests** qua. Image `csms-app:ci-audit-fixed` dựng lại thành công, chứa setuptools **84.0.0**, app/db khởi động healthy trên project nghiệm thu riêng.
- Bộ tích hợp trên image mới đạt **5/5** trong **70,71 giây**: 10 test migration/seed PostgreSQL, thời gian server khi trụ lệch +5 giờ, 50 socket/200 connector/SSE, ba vòng dừng/bật simulator và candidate lỗi giữ bản cũ healthy. Project `csms-ci-audit-check` được dọn sau kiểm tra; không dùng database ứng dụng có sẵn.
- Bản sửa chưa commit/push; các run GitHub cũ vẫn đỏ vì chúng kiểm tra commit chưa có ràng buộc dependency mới. Cần push commit chứa bản sửa để có kết quả CI/CD trên GitHub mới; chạy lại run cũ sẽ dùng code cũ.

## Các điều kiện còn thiếu để chốt Done

1. **GitHub CI:** push bản sửa setuptools và chạy workflow của commit mới, đo <5 phút, chứng minh lint lỗi làm pipeline đỏ và bật required checks/branch protection để chặn merge. Đã xác nhận lint/typecheck GitHub của `255bd32` qua nhưng audit fail; kết quả local sau sửa không thay thế run GitHub mới. Build runtime lạnh trên máy này từng mất hơn 5 phút; việc tách dev tool và cache giúp giảm nhưng không đảm bảo SLA GitHub.
2. **Staging:** người dùng xác nhận chưa có staging. Khi có server, cần cấu hình secrets, thử deploy <10 phút/failure và chạy lại các AC mạng. Các bài tương ứng đã có bộ kiểm tra local Docker chạy lại được.
3. **Giao diện trực quan:** đo layout 20 trụ không cuộn ngang, tải <2 giây, update/restart bằng browser. Logic nguồn dữ liệu/form/Reset/reconnect/mô phỏng đã có 25 test JS; công cụ browser trước đó đã từ chối quyền localhost, nên chưa có chứng cứ quan sát UI.
4. **DoD nhóm:** một thành viên khác duyệt code và so coverage phần sửa với baseline tương đương. Đã có coverage XML nhưng chưa có baseline để khẳng định tiêu chí “không giảm”.

Theo yêu cầu người dùng, giữ nguyên workbook và bỏ qua cột trạng thái khi đánh giá nội dung. Không dùng các tài liệu nghiệm thu cũ trong `ketqua` để tự khẳng định CI/staging của phiên bản mới đã qua.
