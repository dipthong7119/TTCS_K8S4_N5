# Quy tắc cho AI Agent khi vibe-code dự án CSMS

> File này dành cho **bất kỳ AI agent nào** (Claude Code, Cursor, Copilot, v.v.) được giao
> sinh/sửa code trong repo `TTCS_K8S4_N5`. Đọc file này **trước tiên**, sau đó đọc 2 file
> tham chiếu bắt buộc bên dưới. Không bắt đầu viết code nếu chưa đọc cả ba.

## 0. Ba tài liệu phải đọc theo đúng thứ tự

1. **File này** (`00_QUY_TAC_AGENT.md`) — luật chơi, giới hạn phạm vi, việc được/không được làm.
2. **`01_CODEBASE_MAP.md`** — file này đặt ở thư mục nào, quy ước đặt tên, giới hạn cứng cho `backend/` và `frontend/`.
3. **`02_DAC_TA_DU_AN.md`** — toàn bộ nghiệp vụ: Product Goal, sprint, epic, story (kèm Acceptance Criteria dạng Given/When/Then), task kỹ thuật, rủi ro, DoD/DoR.

Nếu một yêu cầu của người dùng mâu thuẫn với 3 file này, **dừng lại và hỏi lại** thay vì tự suy diễn hoặc tự "sáng tạo" giải pháp khác.

## 1. Phạm vi được phép làm

- Chỉ code cho **story/task đã có ID cụ thể** trong `02_DAC_TA_DU_AN.md` (dạng `S-xx` cho story, `T-xx` cho task, `K-xx` cho spike). Khi bắt đầu một việc, luôn nêu rõ đang làm ID nào trong câu trả lời/commit message.
- Không tự bịa thêm tính năng, bảng dữ liệu, endpoint, hay màn hình ngoài những gì đã liệt kê trong đặc tả, kể cả khi nó "hợp lý" hoặc "tiện".
- Story/Task nào trong đặc tả có ghi **"Chưa refine"** hoặc **"tier Later"** với SP thô: đây là backlog chưa đủ chi tiết để code. Agent phải liệt kê rõ những điểm còn thiếu (ghi trong cột NFR/ghi chú của story đó) và hỏi lại người dùng/Product Owner để chốt, **không tự quyết định thay**.
- Việc thuộc Epic có `Deps` (phụ thuộc) chưa Done thì không code trước — trừ khi người dùng xác nhận rõ muốn làm trước.

## 2. Ranh giới kỹ thuật cứng (không thương lượng)

Đây là các luật đã có sẵn trong `01_CODEBASE_MAP.md`, nhắc lại vì vi phạm là lỗi nghiêm trọng:

- **Không tạo thư mục mới** ngoài cấu trúc đã định nghĩa. Nếu thấy cần một vị trí mới, dừng lại và hỏi thay vì tự tạo.
- **Không tạo file `_v2`, `_final`, `_copy`, `_new`, `_old`.** Luôn sửa trực tiếp file gốc; lịch sử để Git lo.
- **Mọi thay đổi schema CSDL đi qua Alembic migration.** Không sửa model SQLAlchemy rồi bỏ qua bước tạo migration.
- `dev_tools/ocpp_simulator/` (trụ sạc giả lập) **không được import bất kỳ logic nào từ `app/`** — nó là client độc lập gọi lên server để test khách quan. Không viết thêm code phần cứng/firmware C/C++ ở bất cứ đâu — toàn bộ "trụ sạc" trong dự án này là phần mềm.
- `routers/` chỉ gọi vào `services/` hoặc DB qua hàm dùng chung; không viết business logic phức tạp trực tiếp trong router.
- Biến môi trường **chỉ được đọc ở `app/config.py`**; không rải `os.getenv` khắp nơi, không hardcode secret trong mã nguồn.
- Frontend: **cấm** `<script>` nghiệp vụ inline trong `.html`; logic JS của từng trang để ở `static/js/pages/`; **mọi** lời gọi API đi qua `static/js/api_client.js`, cấm `fetch()` rải rác.
- Không viết script debug/test dùng một lần rồi commit lên nhánh chính.

## 3. Quy tắc nghiệp vụ xuyên suốt (rút ra từ đặc tả, áp dụng cho mọi story liên quan)

- **Chống trùng / idempotency** phải dựa vào ràng buộc ở cơ sở dữ liệu, không dựa vào biến trong bộ nhớ tiến trình (áp dụng cho: xử lý tin nhắn OCPP trùng mã — S-14; webhook nạp ví gửi lại — S-39; đặt chỗ trùng — S-49). Một tin nhắn/sự kiện xử lý hai lần phải cho kết quả giống hệt xử lý một lần.
- **Tiền luôn lưu bằng số nguyên (đồng)**, không dùng số thực; quy tắc làm tròn phải khai báo rõ một chỗ duy nhất và áp dụng nhất quán.
- **Sổ cái ví (`ledger`) và nhật ký (`audit_logs`) chỉ được phép chèn (INSERT) và đọc** — cấm UPDATE/DELETE từ tầng ứng dụng; số dư luôn suy ra từ tổng sổ cái, không lưu như một cột cập nhật tại chỗ.
- **Phân quyền theo vai trò**: lọc dữ liệu theo quyền sở hữu phải nằm ở tầng truy vấn (query), không lọc ở giao diện; route mới không khai báo quyền thì mặc định bị từ chối (deny-by-default).
- **Không log dữ liệu định danh cá nhân**: mã thẻ (`idTag`) chỉ log 4 ký tự cuối; mật khẩu/token không bao giờ log; không log chuỗi kết nối CSDL.
- **Mật khẩu hash bằng argon2id.**
- Mọi phép tính theo ngày/khung giờ (biểu giá, đối soát) dùng **múi giờ của trạm**, không dùng UTC trần trụi khi hiển thị cho người dùng.
- Dữ liệu cá nhân tài xế (vị trí, lịch sử di chuyển) chịu ràng buộc Nghị định 13/2023/NĐ-CP — đây là **giới hạn pháp lý**, agent không tự ý quyết định phạm vi xoá/ẩn danh hoá dữ liệu (xem S-57); nêu rõ cần người có thẩm quyền xác nhận. **Agent không đưa tư vấn pháp lý.**

## 4. Cách agent nên làm việc trên một story/task

1. Xác định ID story/task cần làm, đọc đúng đoạn tương ứng trong `02_DAC_TA_DU_AN.md` (Story, AC, Deps, NFR).
2. Kiểm tra Deps đã Done chưa; nếu công cụ có quyền chạy lệnh, có thể kiểm tra qua trạng thái task trong tracker của team (không suy đoán).
3. Xác định vị trí file theo `01_CODEBASE_MAP.md`; nếu task đã có "mẫu" tham chiếu (ví dụ "theo mẫu T-16"), mở file mẫu đó trước khi viết file mới để giữ đúng cấu trúc.
4. Viết code + test đơn vị cho nhánh logic mới (bắt buộc theo DoD).
5. Nếu story "chạm tiền": chuẩn bị bộ ca kiểm thử có đáp án tính tay riêng (không sinh đáp án bằng chính thuật toán vừa viết).
6. Nếu story "chạm tin nhắn OCPP": đảm bảo xử lý hai lần cho kết quả giống hệt một lần (test lại theo kịch bản gửi trùng).
7. Nếu có job nền: test chạy job hai lần liên tiếp không gây tác dụng phụ.
8. Tự đối chiếu với checklist DoD ở mục 7 của `02_DAC_TA_DU_AN.md` trước khi báo hoàn thành.

## 5. Khi không chắc

Nếu đặc tả thiếu, mơ hồ, hoặc yêu cầu của người dùng vượt phạm vi 3 tài liệu trên: **dừng lại, nêu rõ điểm còn thiếu, và hỏi** — không tự phịa để "cho xong việc". Đây là quy tắc quan trọng nhất trong file này.
