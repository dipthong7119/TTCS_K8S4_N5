# ĐẶC TẢ DỰ ÁN — Nền tảng vận hành trạm sạc xe điện (CSMS)

> Nguồn: tổng hợp và cấu trúc lại từ `sprint1.xlsx` (kế hoạch Scrum) và `01_CODEBASE_MAP.md` (cấu trúc mã nguồn).
> Tài liệu này là **nguồn tham chiếu nghiệp vụ duy nhất**. Không tự suy diễn yêu cầu ngoài những gì ghi ở đây — phần nào ghi "Chưa refine" nghĩa là **chưa đủ để code**, phải dừng và hỏi lại Product Owner / người dùng trước khi triển khai.

## 1. Thông tin chung

| Trường | Giá trị |
| --- | --- |
| Tên dự án | Nền tảng vận hành trạm sạc xe điện (CSMS) |
| Độ dài sprint | 1 tuần |
| Ngày làm việc / sprint | 5 |
| Đơn vị ước lượng | story point (Fibonacci) |
| Product Goal | Đơn vị vận hành mạng lưới trạm sạc nắm được mọi phiên sạc theo thời gian thực qua giao thức OCPP, tính đúng tiền theo biểu giá nhiều khung, không để trạm vượt công suất, và đối soát được doanh thu khớp với số kWh đã cấp |
| Kinh nghiệm team | thực tập / mới ra trường |
| Quen Scrum | mới áp dụng |
| Ràng buộc tuân thủ | có — thanh toán trực tuyến (chỉ dùng sandbox) và dữ liệu cá nhân tài xế gồm vị trí và lịch sử di chuyển (Nghị định 13/2023/NĐ-CP) |

## 2. Kiến trúc & quy ước mã nguồn

Xem đầy đủ tại `01_CODEBASE_MAP.md` (nguồn sự thật duy nhất về vị trí file). Tóm tắt bắt buộc:

- `backend/` — toàn bộ Python/FastAPI: `app/models` (SQLAlchemy, 1 file = 1 bảng), `app/schemas` (Pydantic), `app/routers` (endpoint, gọi `services`, không viết nghiệp vụ trực tiếp), `app/core` (security, deps dùng chung), `app/services` (business logic thuần), `app/dev_tools/ocpp_simulator` (giả lập trụ sạc — **không được import logic từ `app/`**), `alembic/` (migration bắt buộc cho mọi thay đổi schema).
- `frontend/` — HTML Jinja2 (`templates/`) + Vanilla JS (`static/js/`): **cấm** script nghiệp vụ inline trong `.html`; script trang riêng để ở `static/js/pages/`; **mọi** gọi API phải qua `static/js/api_client.js`, cấm `fetch()` tự do.
- Không tạo thư mục mới ngoài cấu trúc đã có; không tạo file `_v2`/`_final`/`_copy`; không tự tạo file phần cứng/firmware — toàn bộ "trụ sạc" trong dự án là phần mềm giả lập ở `dev_tools/ocpp_simulator/`.
- Mọi thay đổi cơ sở dữ liệu phải qua migration Alembic, không sửa model rồi bỏ qua migration.

## 3. Lộ trình Sprint

| Sprint | Sprint Goal | Capacity (SP) | Đã xếp (SP) |
| --- | --- | --- | --- |
| 1 | Chủ trạm khai báo được trạm và trụ trên môi trường staging chạy thật | 12 | 12 |
| 2 | Trụ ảo nối vào hệ thống được xác thực, và vận hành viên thấy đúng trạng thái mọi trụ kể cả khi kết nối chập chờn | 20 | 20 |
| 3 | Một phiên sạc chạy trọn vẹn từ lúc cắm tới lúc rút với số kWh đúng, dù trụ có mất kết nối giữa chừng | 20 | 20 |
| 4 | Phiên sạc ra đúng số tiền theo biểu giá nhiều khung giờ và tài xế đọc được vì sao ra số đó | 20 | 20 |
| 5 | Tài xế nạp ví và tiền tự trừ khi sạc xong, số dư không sai một đồng | 20 | 20 |
| 6 | Trạm không bao giờ vượt hạn mức công suất dù nhiều xe cùng sạc | 20 | 19 |
| 7 | Tài xế tìm được trạm còn trống, đặt được chỗ, và chỗ đã đặt chắc chắn là của họ | 20 | 19 |
| 8 | Cuối kỳ, doanh thu đối soát khớp với số kWh đã cấp và chia được cho từng đối tác | 20 | 20 |

## 4. Danh mục Epic

| ID | Epic | Tier | Priority | Deps | Owner |
| --- | --- | --- | --- | --- | --- |
| E-01 | Hạ tầng, CI/CD và môi trường | Ready | Must | không | cả team |
| E-02 | Tài khoản, đối tác và phân quyền | Ready | Must | E-01 | cả team |
| E-03 | Trạm sạc, trụ và đầu nối | Ready | Must | E-02 | cả team |
| E-04 | Kết nối OCPP và phiên sạc | Ready | Must | E-03 | cả team |
| E-05 | Biểu giá và tính tiền | Next | Must | E-04 | chưa phân |
| E-06 | Ví và thanh toán | Next | Must | E-05 | chưa phân |
| E-07 | Đặt chỗ trụ sạc | Later | Should | E-06 | chưa phân |
| E-08 | Phân bổ công suất | Later | Must | E-04 | chưa phân |
| E-09 | Đối soát và chia doanh thu | Later | Must | E-06 | chưa phân |
| E-10 | Giám sát vận hành và bảo vệ dữ liệu cá nhân | Ready | Must | E-04 | cả team |
| E-11 | Ứng dụng tài xế | Ready | Must | E-04 | cả team |

## 5. Chi tiết Epic — Backlog — Task

### E-01 — Hạ tầng, CI/CD và môi trường

**Tier:** Ready · **Priority:** Must · **Status:** Todo · **Deps:** không · **Owner:** cả team

**Mô tả:** Môi trường chạy được từ ngày đầu: khung dự án, cơ sở dữ liệu, pipeline CI, triển khai staging bằng Docker, và bộ trụ ảo chạy chung với ứng dụng. Dự án này cần chạy nhiều trụ ảo cùng lúc nên môi trường phải dựng bằng container ngay từ đầu; không có DevOps nên việc này nằm trong sprint 1, không để tới lúc cần.

**Acceptance (mức epic):** Mọi thành viên chạy được dự án và 20 trụ ảo bằng một lệnh; mỗi lần merge vào nhánh chính thì staging tự cập nhật; CI chặn merge khi kịch bản trụ ảo thất bại

**NFR:** bí mật nạp từ biến môi trường, không nằm trong mã nguồn

#### S-01 — Khung ứng dụng chạy được trên staging  *[Story, Sprint 1]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 3 · **Deps:** không · **Owner:** cả team
- **User story:** Là thành viên phát triển tôi muốn có khung ứng dụng chạy được trên staging để mọi story sau đều có chỗ chạy thật thay vì chỉ chạy trên máy cá nhân
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử máy chủ staging đã sẵn sàng, Khi merge vào nhánh chính, Thì pipeline build, chạy test và triển khai tự động, và trang chủ trả về HTTP 200
  - Giả sử một bài test thất bại, Khi pipeline chạy, Thì dừng lại và không triển khai
  - Giả sử thành viên mới lấy mã nguồn về, Khi chạy lệnh khởi động ghi trong README, Thì ứng dụng và cơ sở dữ liệu chạy được trên máy cá nhân
  - Giả sử triển khai thất bại giữa chừng, Khi kiểm tra staging, Thì phiên bản cũ vẫn đang chạy
- **NFR / ràng buộc kỹ thuật:** bí mật nạp từ biến môi trường; log không in chuỗi kết nối cơ sở dữ liệu

  **Task kỹ thuật của S-01:**

  - **T-01 — Dựng khung dự án và kết nối cơ sở dữ liệu** *(Sprint 1, Todo)*
    - Mô tả: Khởi tạo dự án, cấu hình kết nối PostgreSQL, chạy được migration đầu tiên. Viết `docker-compose.yml` gồm ứng dụng và cơ sở dữ liệu để cả team dùng chung một cấu hình. Migration này là mẫu đặt tên bảng và cột cho mọi migration sau — đặt tên theo `snake_case`, khoá chính `id`, cột thời gian `created_at`/`updated_at`.
    - AC: Chạy `docker compose up` rồi khởi động ứng dụng thì kết nối được cơ sở dữ liệu, migration chạy sạch và chạy lùi được
    - Deps: không
    - NFR: chuỗi kết nối đọc từ biến môi trường
    - Owner: cả team
  - **T-02 — Pipeline CI chạy build, lint, test** *(Sprint 1, Todo)*
    - Mô tả: Cấu hình CI chạy build, lint, test trên mỗi push và mỗi pull request. Tạo sẵn một test đơn vị rỗng làm chỗ cho test sau bám vào.
    - AC: Push commit cố ý sai lint thì pipeline đỏ và chặn merge; commit sạch thì xanh dưới 5 phút
    - Deps: T-01
    - NFR: pipeline chạy xong dưới 5 phút để không làm chậm nhịp sprint 1 tuần
    - Owner: cả team
  - **T-03 — Triển khai tự động lên staging bằng Docker** *(Sprint 1, Todo)*
    - Mô tả: Đóng gói ứng dụng thành image, đẩy lên máy chủ riêng, chạy bằng Docker. Nối vào pipeline ở T-02 sau bước test. Viết bước kiểm sức khoẻ: gọi trang chủ, không trả 200 thì giữ container cũ.
    - AC: Merge vào nhánh chính thì staging chạy phiên bản mới trong 10 phút, không cần thao tác tay; triển khai hỏng thì phiên bản cũ còn nguyên
    - Deps: T-02
    - NFR: triển khai thất bại thì giữ nguyên phiên bản cũ
    - Owner: cả team

#### S-26 — Bộ trụ ảo chạy trong `docker-compose` và trong CI  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Should / Todo
- **SP:** 2 · **Deps:** S-21 · **Owner:** cả team
- **User story:** Là thành viên phát triển tôi muốn bật 20 trụ ảo bằng một lệnh và CI tự chạy chúng để mỗi lần sửa mã còn biết có phá vỡ bảo đảm về phiên sạc không, thay vì tin vào lời "trên máy tôi chạy được"
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử đã có `docker-compose.yml` từ T-01, Khi chạy lệnh khởi động kèm số trụ, Thì đúng số trụ ảo đó nối vào hệ thống và hiện trên màn hình theo dõi
  - Giả sử một pull request sửa mã xử lý tin nhắn OCPP, Khi CI chạy, Thì kịch bản trụ ảo chạy trọn và pull request bị chặn nếu kịch bản thất bại
  - Giả sử simulator được cập nhật phiên bản, Khi đổi thẻ phiên bản trong compose, Thì mọi thứ khác không phải sửa
- **NFR / ràng buộc kỹ thuật:** kịch bản trụ ảo trong CI chạy xong dưới 5 phút; simulator ghim phiên bản cụ thể

  **Task kỹ thuật của S-26:**

  - **T-55 — Dịch vụ trụ ảo trong `docker-compose` với số lượng cấu hình được** *(Sprint 3, Todo)*
    - Mô tả: Thêm dịch vụ simulator đã chọn ở K-01 vào `docker-compose.yml`, nhận biến môi trường số trụ và địa chỉ máy chủ. Mỗi trụ ảo dùng một mã đã seed sẵn trong bảng `charge_points`.
    - AC: Chạy với số trụ 20 thì màn hình theo dõi hiện 20 trụ trực tuyến trong vòng 1 phút
    - Deps: T-46
    - NFR: mã trụ ảo seed tách khỏi dữ liệu thật bằng tiền tố riêng
    - Owner: cả team
  - **T-56 — Bước CI chạy kịch bản 20 trụ ảo và chặn merge khi thất bại** *(Sprint 3, Todo)*
    - Mô tả: Thêm bước vào pipeline ở T-02: dựng ứng dụng và trụ ảo, chạy kịch bản ngắt–nối ở T-46, đọc kết quả. Chạy sau bước test đơn vị để không tốn thời gian khi test đơn vị đã đỏ.
    - AC: Cố ý làm sai phần khôi phục phiên thì pull request bị chặn kèm log nêu phiên nào sai
    - Deps: T-55
    - NFR: log kết quả ghi mã phiên và số kWh mong đợi so với thực tế
    - Owner: cả team

#### S-62 — Sao lưu cơ sở dữ liệu hằng ngày và khôi phục được  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-41 · **Owner:** chưa phân
- **User story:** Là quản trị hệ thống tôi muốn có bản sao lưu mỗi ngày và đã từng khôi phục thử để mất máy chủ không đồng nghĩa mất lịch sử phiên và số dư ví
- **Acceptance Criteria (Given/When/Then):**
  - Có bản sao lưu mỗi đêm và một lần khôi phục thử thành công lên môi trường trống. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt nơi lưu bản sao và thời gian giữ; bản sao chứa dữ liệu cá nhân nên phải mã hoá

### E-02 — Tài khoản, đối tác và phân quyền

**Tier:** Ready · **Priority:** Must · **Status:** Todo · **Deps:** E-01 · **Owner:** cả team

**Mô tả:** Năm vai trò dùng chung hệ thống nhưng thấy dữ liệu khác nhau. Đặc biệt: chủ trạm chỉ được thấy trạm của mình, không thấy doanh thu của đối tác khác. Quản trị viên tạo tài khoản và gán vai trò, không cho tự đăng ký vai trò.

**Acceptance (mức epic):** Chủ trạm A gọi API xem doanh thu trạm của chủ trạm B thì bị từ chối ở máy chủ; không route nào mở mà chưa khai quyền

**NFR:** mật khẩu hash bằng argon2id; không log mật khẩu và token

#### S-02 — Đăng nhập bằng email và mật khẩu, khoá tạm khi sai nhiều lần  *[Story, Sprint 1]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-01 · **Owner:** cả team
- **User story:** Là người dùng của hệ thống tôi muốn đăng nhập bằng email và mật khẩu để vào được phần việc của mình mà kẻ đoán mật khẩu không vào được
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử thông tin đúng, Khi đăng nhập, Thì tạo phiên đăng nhập và chuyển tới trang chính của vai trò đó
  - Giả sử sai mật khẩu, Khi đăng nhập, Thì báo lỗi chung "email hoặc mật khẩu không đúng", không tiết lộ email có tồn tại hay không
  - Giả sử nhập sai mật khẩu 5 lần liên tiếp, Khi thử lần thứ 6, Thì khoá đăng nhập 15 phút kể cả khi nhập đúng
  - Giả sử phiên đăng nhập đã hết hạn, Khi gọi API bất kỳ, Thì trả về 401 và chuyển về trang đăng nhập
- **NFR / ràng buộc kỹ thuật:** mật khẩu hash bằng argon2id; đếm lần sai theo tài khoản và theo IP

  **Task kỹ thuật của S-02:**

  - **T-04 — Bảng `users`, `roles` kèm migration và seed năm vai trò** *(Sprint 1, Todo)*
    - Mô tả: Thêm bảng `users`, `roles`, bảng nối `user_roles`. Seed sẵn năm vai trò: tài xế, chủ trạm, vận hành viên, kế toán, quản trị. Đặt tên cột theo mẫu migration ở T-01.
    - AC: Migration tiến và lùi được; `users.email` có ràng buộc unique; sau seed có đúng năm dòng trong `roles`
    - Deps: T-01
    - NFR: cột mật khẩu đủ dài cho hash argon2id
    - Owner: cả team
  - **T-05 — Form đăng nhập, tạo phiên, đếm lần sai và khoá tạm** *(Sprint 1, Todo)*
    - Mô tả: Form đăng nhập, kiểm tra thông tin, tạo phiên đăng nhập bằng cookie httpOnly. Lưu số lần sai và thời điểm khoá vào bảng `users`, không lưu trong bộ nhớ tiến trình. Bố cục form này là mẫu cho mọi form sau.
    - AC: Đăng nhập đúng thì vào trang chính; sai 5 lần thì lần thứ 6 bị khoá 15 phút; khởi động lại ứng dụng thì khoá vẫn còn
    - Deps: T-04
    - NFR: thông báo lỗi không tiết lộ email có tồn tại hay không
    - Owner: cả team

#### S-03 — Mỗi vai trò chỉ thấy và thao tác được phần việc của mình  *[Story, Sprint 1]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-02 · **Owner:** cả team
- **User story:** Là chủ trạm tôi muốn dữ liệu trạm và doanh thu của mình không lọt sang đối tác khác để yên tâm đưa trạm lên nền tảng dùng chung
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tài khoản có vai trò chủ trạm, Khi mở danh sách trạm, Thì chỉ thấy trạm thuộc sở hữu của mình
  - Giả sử chủ trạm A gọi thẳng API xem trạm của chủ trạm B bằng công cụ dòng lệnh, Khi máy chủ nhận yêu cầu, Thì trả về 403 và ghi nhật ký lần thử đó
  - Giả sử tài khoản tài xế gọi API dành cho vận hành viên, Khi máy chủ nhận yêu cầu, Thì trả về 403
  - Giả sử một route mới được thêm mà chưa khai báo quyền, Khi gọi tới, Thì bị từ chối mặc định
- **NFR / ràng buộc kỹ thuật:** lọc theo quyền sở hữu ở tầng truy vấn, không lọc ở giao diện

  **Task kỹ thuật của S-03:**

  - **T-06 — Middleware kiểm vai trò, mặc định từ chối route chưa khai quyền** *(Sprint 1, Todo)*
    - Mô tả: Một lớp middleware kiểm vai trò trước khi vào handler, thay vì rải lệnh `if` trong từng handler. Route khai báo vai trò được phép bằng một khai báo ngắn cạnh định nghĩa route; không khai thì chặn.
    - AC: Gọi route chưa khai quyền bằng tài khoản quản trị vẫn nhận 403; khai quyền xong thì đúng vai trò mới qua được
    - Deps: T-05
    - NFR: mặc định là từ chối — route mới không khai báo quyền thì bị chặn
    - Owner: cả team
  - **T-07 — Lọc theo quyền sở hữu ở tầng truy vấn và test 403 bằng curl** *(Sprint 1, Todo)*
    - Mô tả: Viết hàm truy vấn dùng chung nhận tài khoản hiện tại và tự thêm điều kiện chủ sở hữu vào mọi truy vấn trạm. Viết test gọi API bằng hai tài khoản chủ trạm khác nhau. Xem cách T-06 lấy tài khoản hiện tại để dùng lại.
    - AC: Chủ trạm A gọi API trạm của B bằng curl nhận 403 và có một dòng nhật ký; test tự động phủ ca này
    - Deps: T-06
    - NFR: điều kiện sở hữu nằm trong một hàm duy nhất, không chép tay vào từng truy vấn
    - Owner: cả team

#### S-61 — Quản trị viên quản lý tài khoản và gán vai trò  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-03 · **Owner:** chưa phân
- **User story:** Là quản trị hệ thống tôi muốn tạo, khoá tài khoản và gán vai trò để nhân sự mới vào việc được và người nghỉ không còn vào được
- **Acceptance Criteria (Given/When/Then):**
  - Tạo tài khoản kèm vai trò, khoá tài khoản làm phiên đang mở hết hiệu lực, đổi vai trò có hiệu lực ở lần gọi API kế tiếp. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt có cho một tài khoản nhiều vai trò không

### E-03 — Trạm sạc, trụ và đầu nối

**Tier:** Ready · **Priority:** Must · **Status:** Todo · **Deps:** E-02 · **Owner:** cả team

**Mô tả:** Cây dữ liệu ba tầng: một trạm có nhiều trụ, một trụ có nhiều đầu nối. Mã định danh trụ phải khớp với mã trụ dùng khi kết nối OCPP, nếu không trụ thật sẽ không nối được. Trạm có trạng thái hoạt động để chủ trạm tạm ngừng khi bảo trì.

**Acceptance (mức epic):** Đăng ký trạm có trụ và đầu nối; mã trụ là duy nhất trên toàn hệ thống; trạm tạm ngừng không nhận phiên mới

**NFR:** mã trụ không được đổi sau khi đã có phiên sạc, vì phiên cũ tham chiếu tới nó

#### S-04 — Chủ trạm tạo và sửa thông tin trạm sạc  *[Story, Sprint 1]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-03 · **Owner:** cả team
- **User story:** Là chủ trạm tôi muốn khai báo trạm với tên, địa chỉ và toạ độ để tài xế tìm thấy trạm và hệ thống biết trạm này thuộc về ai
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử đã đăng nhập bằng vai trò chủ trạm, Khi tạo trạm với tên, địa chỉ và toạ độ hợp lệ, Thì trạm được lưu ở trạng thái chưa hoạt động và gắn với tài khoản của tôi
  - Giả sử toạ độ nằm ngoài dải hợp lệ, Khi lưu, Thì báo lỗi ngay tại ô toạ độ và không tạo bản ghi
  - Giả sử trạm đã có, Khi sửa tên hoặc địa chỉ, Thì thay đổi hiện ngay trong danh sách trạm của tôi
  - Giả sử tôi bấm lưu hai lần liên tiếp, Khi máy chủ xử lý, Thì chỉ tạo một trạm
- **NFR / ràng buộc kỹ thuật:** toạ độ lưu ở dạng số thực đủ độ chính xác để tìm trạm gần ở S-47

  **Task kỹ thuật của S-04:**

  - **T-08 — Bảng `stations` kèm migration và liên kết chủ sở hữu** *(Sprint 1, Todo)*
    - Mô tả: Thêm bảng `stations` có khoá ngoại tới `users` làm chủ sở hữu, cột trạng thái hoạt động, toạ độ kiểu số thực. Theo mẫu migration ở T-04.
    - AC: Migration tiến và lùi được; xoá tài khoản chủ trạm còn trạm thì bị chặn bởi khoá ngoại
    - Deps: T-04
    - NFR: có chỉ mục trên cột chủ sở hữu vì mọi truy vấn của chủ trạm lọc theo cột này
    - Owner: cả team
  - **T-09 — Màn hình tạo, sửa và danh sách trạm của chủ trạm** *(Sprint 1, Todo)*
    - Mô tả: Form tạo/sửa trạm và danh sách trạm của tôi. Dùng lại bố cục form và cách hiện lỗi tại ô của form đăng nhập T-05. Danh sách gọi qua hàm truy vấn có lọc sở hữu ở T-07.
    - AC: Tạo, sửa, xem danh sách trạm đều chạy; lỗi nhập liệu hiện ngay tại ô sai; nút lưu bị vô hiệu trong lúc đang gửi
    - Deps: T-08
    - NFR: form gửi đi phải chặn bấm hai lần liên tiếp
    - Owner: cả team

#### S-05 — Chủ trạm thêm trụ và đầu nối vào trạm, mã trụ là duy nhất  *[Story, Sprint 1]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 1 · **Deps:** S-04 · **Owner:** cả team
- **User story:** Là chủ trạm tôi muốn khai báo từng trụ với mã định danh và số đầu nối để trụ thật cắm điện xong là nối vào được hệ thống bằng đúng mã đó
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trạm đã tồn tại, Khi thêm một trụ có mã chưa dùng và số đầu nối từ 1 tới 4, Thì trụ được tạo kèm đúng số đầu nối, mỗi đầu nối ở trạng thái chưa rõ
  - Giả sử nhập mã trụ đã tồn tại ở bất kỳ trạm nào, Khi lưu, Thì bị chặn kèm thông báo mã đã được dùng
  - Giả sử trụ đã có phiên sạc, Khi sửa mã định danh của nó, Thì bị chặn kèm lý do
- **NFR / ràng buộc kỹ thuật:** ràng buộc unique nằm ở cơ sở dữ liệu, không chỉ kiểm ở form

  **Task kỹ thuật của S-05:**

  - **T-10 — Bảng `charge_points`, `connectors` kèm migration và ràng buộc unique** *(Sprint 1, Todo)*
    - Mô tả: Hai bảng con của `stations` theo quan hệ cha–con hai tầng. `charge_points.code` unique toàn hệ thống và có chỉ mục vì mọi kết nối OCPP tra cứu theo cột này. Theo mẫu T-08.
    - AC: Migration tiến và lùi được; chèn hai trụ cùng `code` thì cơ sở dữ liệu từ chối
    - Deps: T-08
    - NFR: `connectors` có cột số thứ tự khớp với `connectorId` trong tin nhắn OCPP, bắt đầu từ 1
    - Owner: cả team
  - **T-11 — Form thêm trụ kèm số đầu nối, chặn mã trùng ngay tại ô nhập** *(Sprint 1, Todo)*
    - Mô tả: Form thêm trụ trong trang chi tiết trạm, kiểm mã trùng bằng một lời gọi API khi rời ô nhập, và kiểm lại ở máy chủ khi lưu. Bố cục theo T-09.
    - AC: Nhập mã đã có thì ô nhập báo đỏ trước khi bấm lưu; lách qua giao diện gửi thẳng API thì máy chủ vẫn từ chối
    - Deps: T-10
    - NFR: không tin kết quả kiểm ở trình duyệt, máy chủ là nơi quyết
    - Owner: cả team

#### S-66 — Chủ trạm đưa trạm vào hoạt động hoặc tạm ngừng  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 2 · **Deps:** S-47 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn bật trạm khi đã lắp xong và tạm ngừng khi bảo trì để tài xế không tới một trạm đang sửa
- **Acceptance Criteria (Given/When/Then):**
  - Trạm tạm ngừng không hiện trong tìm kiếm của tài xế và trụ của nó từ chối phiên mới; phiên đang chạy vẫn kết thúc bình thường. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt có cho tạm ngừng từng trụ riêng lẻ không

### E-04 — Kết nối OCPP và phiên sạc

**Tier:** Ready · **Priority:** Must · **Status:** Todo · **Deps:** E-03 · **Owner:** cả team

**Mô tả:** Lõi kỹ thuật của cả dự án. Trụ sạc là client chủ động mở kết nối WebSocket tới hệ thống, rồi hai bên trao đổi tin nhắn OCPP 1.6J suốt vòng đời phiên sạc: khởi động, nhịp tim, trạng thái đầu nối, xác thực thẻ, bắt đầu, số đo, kết thúc, và các lệnh từ máy chủ xuống trụ. Kết nối hay đứt, tin nhắn hay tới muộn hoặc tới hai lần — hệ thống phải đúng trong mọi trường hợp đó.

**Acceptance (mức epic):** Chạy 20 trụ ảo, ngắt kết nối ngẫu nhiên giữa phiên rồi nối lại, thì mọi phiên đều kết thúc với số kWh đúng và không phiên nào bị nhân đôi

**NFR:** một tin nhắn xử lý hai lần phải cho kết quả giống hệt xử lý một lần

#### K-01 — Trụ sạc ảo nối được vào máy chủ WebSocket tối giản  *[Spike, Sprint 1]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-01 · **Owner:** cả team
- **User story:** Spike timebox 2 ngày cho 2 người, có người hướng dẫn ngồi cùng buổi đầu. Tải đặc tả OCPP 1.6J, chạy thử một simulator mã nguồn mở, nối nó vào một máy chủ WebSocket tối giản, và ghi lại chuỗi tin nhắn thật của một phiên sạc từ lúc trụ khởi động tới lúc rút súng. Chỉ đọc phần đặc tả của 8 tin nhắn: `BootNotification`, `Heartbeat`, `StatusNotification`, `Authorize`, `StartTransaction`, `MeterValues`, `StopTransaction`, `Reset`. Kết quả quyết định cấu trúc bảng và cách xử lý tin nhắn ở S-06 tới S-21.
- **Acceptance Criteria (Given/When/Then):**
  - Đầu ra là một tài liệu ngắn có: simulator đã chọn kèm lý do, bản ghi chuỗi tin nhắn của một phiên hoàn chỉnh, và danh sách trường dữ liệu của từng tin nhắn mà hệ thống phải lưu
- **NFR / ràng buộc kỹ thuật:** không viết mã sản phẩm trong spike; kết quả là kiến thức và mã thử vứt đi được

#### S-06 — Trụ đã đăng ký kết nối được qua WebSocket, trụ lạ bị từ chối  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-05, K-01 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn chỉ những trụ đã đăng ký mới kết nối được vào hệ thống để không ai cắm một thiết bị lạ vào và bơm dữ liệu giả
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ có mã đã đăng ký ở S-05, Khi trụ mở kết nối WebSocket tới đường dẫn chứa mã đó, Thì kết nối được chấp nhận và giữ mở
  - Giả sử trụ dùng mã không có trong hệ thống, Khi mở kết nối, Thì kết nối bị đóng ngay và một dòng nhật ký ghi mã lạ kèm địa chỉ IP
  - Giả sử trụ yêu cầu giao thức con khác `ocpp1.6`, Khi bắt tay WebSocket, Thì bị từ chối
  - Giả sử trụ thuộc trạm đang tạm ngừng, Khi mở kết nối, Thì vẫn được chấp nhận để báo trạng thái, nhưng không được bắt đầu phiên
- **NFR / ràng buộc kỹ thuật:** mã trụ nằm trong đường dẫn WebSocket phải được kiểm tra, không tin dữ liệu trong thân tin nhắn

  **Task kỹ thuật của S-06:**

  - **T-12 — Endpoint WebSocket đọc mã trụ từ đường dẫn và tra bảng `charge_points`** *(Sprint 2, Todo)*
    - Mô tả: Mở endpoint WebSocket dạng `/ocpp/<mã trụ>`, lấy mã trụ từ đường dẫn, tra cứu trong bảng `charge_points` ở T-10, chấp nhận nếu có. Xem bản ghi chuỗi tin nhắn từ K-01 để biết simulator nối vào đường dẫn nào và khai giao thức con gì.
    - AC: Trụ ảo nối vào bằng mã hợp lệ thì kết nối mở và giữ được ít nhất 10 phút không tự đứt
    - Deps: T-10
    - NFR: giữ được ít nhất 50 kết nối đồng thời trên staging
    - Owner: cả team
  - **T-13 — Đóng kết nối của mã lạ và ghi nhật ký lần thử** *(Sprint 2, Todo)*
    - Mô tả: Nhánh từ chối của T-12: mã không có trong bảng thì đóng kết nối với mã đóng chuẩn và ghi log ở mức cảnh báo kèm mã lạ và IP. Không trả về lý do chi tiết cho phía trụ.
    - AC: Nối trụ ảo với mã bịa thì kết nối đóng trong 1 giây và log có đúng một dòng cảnh báo
    - Deps: T-12
    - NFR: không log toàn bộ header của yêu cầu, chỉ log mã và IP
    - Owner: cả team

#### S-07 — Hệ thống đọc và ghi đúng ba loại khung tin nhắn OCPP  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-06 · **Owner:** cả team
- **User story:** Là thành viên phát triển tôi muốn một bộ đọc và ghi khung tin nhắn dùng chung để mọi handler sau chỉ lo nghiệp vụ, không ai phải tự phân tích mảng JSON lần nữa
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ gửi khung `CALL` hợp lệ, Khi hệ thống nhận, Thì tách được mã tin nhắn, tên hành động và tải, rồi chuyển tới đúng handler theo tên hành động
  - Giả sử trụ gửi khung sai định dạng hoặc thiếu trường, Khi hệ thống nhận, Thì trả về khung `CALLERROR` với mã lỗi đúng chuẩn thay vì đóng kết nối
  - Giả sử trụ gửi tên hành động hệ thống chưa hỗ trợ, Khi hệ thống nhận, Thì trả về `CALLERROR` mã `NotImplemented` và ghi log
  - Giả sử hệ thống gửi `CALL` xuống trụ, Khi trụ trả `CALLRESULT`, Thì câu trả lời được khớp đúng với lời gọi theo mã tin nhắn
- **NFR / ràng buộc kỹ thuật:** mã tin nhắn của mỗi lời gọi từ máy chủ phải là duy nhất và được lưu để khớp với câu trả lời

  **Task kỹ thuật của S-07:**

  - **T-14 — Hàm đọc và ghi khung `CALL`, `CALLRESULT`, `CALLERROR`** *(Sprint 2, Todo)*
    - Mô tả: OCPP 1.6J gói mỗi tin nhắn thành một mảng JSON: `[2, mã, hành động, tải]` cho `CALL`, `[3, mã, tải]` cho `CALLRESULT`, `[4, mã, mã lỗi, mô tả, chi tiết]` cho `CALLERROR`. Viết một module thuần, không phụ thuộc WebSocket, gồm hàm đọc và hàm ghi cho ba loại. Bản ghi ở K-01 là dữ liệu mẫu cho test.
    - AC: Đọc đúng mọi khung trong bản ghi K-01; ghi rồi đọc lại cho ra cùng giá trị
    - Deps: T-13
    - NFR: module thuần, test được không cần mở kết nối
    - Owner: cả team
  - **T-15 — Bộ test khung sai định dạng trả về `CALLERROR` đúng mã lỗi** *(Sprint 2, Todo)*
    - Mô tả: Viết test cho các ca: không phải mảng, thiếu phần tử, loại khung lạ, tải không phải đối tượng, hành động chưa hỗ trợ. Mỗi ca đối chiếu mã lỗi với bảng mã lỗi trong đặc tả (`FormationViolation`, `ProtocolError`, `NotImplemented`). Đây là mẫu viết test theo bảng dữ liệu cho các handler sau.
    - AC: Cả năm ca đều trả về `CALLERROR` đúng mã và kết nối vẫn mở sau đó
    - Deps: T-14
    - NFR: test chạy trong CI ở T-02
    - Owner: cả team

#### S-08 — Trụ khởi động được chấp nhận qua `BootNotification`  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-07 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn biết trụ vừa bật lên là loại gì, chạy firmware nào để khi trụ lỗi tôi biết mình đang xử lý thiết bị nào
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ đã đăng ký, Khi gửi `BootNotification` kèm nhà sản xuất và mẫu trụ, Thì hệ thống lưu thông tin đó, trả về `Accepted` kèm giờ máy chủ và khoảng nhịp tim, và đánh dấu trụ trực tuyến
  - Giả sử trụ thuộc trạm bị khoá bởi quản trị viên, Khi gửi `BootNotification`, Thì trả về `Rejected` và trụ không được coi là trực tuyến
  - Giả sử trụ gửi `BootNotification` lần thứ hai trong cùng kết nối, Khi hệ thống nhận, Thì cập nhật thông tin và không tạo bản ghi trụ mới
  - Giả sử trụ gửi tin nhắn khác trước khi được chấp nhận, Khi hệ thống nhận, Thì trả về `CALLERROR` mã `SecurityError`
- **NFR / ràng buộc kỹ thuật:** khoảng nhịp tim là tham số cấu hình, không ghi cứng

  **Task kỹ thuật của S-08:**

  - **T-16 — Handler `BootNotification` lưu nhà sản xuất, mẫu trụ, phiên bản firmware** *(Sprint 2, Todo)*
    - Mô tả: Handler đầu tiên viết theo khung ở T-14; cấu trúc file của nó là mẫu cho mọi handler sau. Đọc các trường `chargePointVendor`, `chargePointModel`, `firmwareVersion` và lưu vào `charge_points`. Thêm cột bằng migration mới theo mẫu T-10.
    - AC: Trụ ảo gửi `BootNotification` thì ba cột trên có dữ liệu và cột trạng thái chuyển sang trực tuyến
    - Deps: T-15
    - NFR: trường thiếu thì lưu rỗng, không từ chối tin nhắn
    - Owner: cả team
  - **T-17 — Trả về trạng thái chấp nhận hoặc từ chối kèm khoảng nhịp tim cấu hình được** *(Sprint 2, Todo)*
    - Mô tả: Phần trả lời của T-16: quyết định `Accepted`/`Rejected` theo trạng thái trụ và trạm, đọc khoảng nhịp tim từ cấu hình, chặn mọi tin nhắn khác cho tới khi trụ được chấp nhận.
    - AC: Trụ ảo nhận `Accepted` kèm `interval` bằng giá trị cấu hình; đổi cấu hình rồi khởi động lại ứng dụng thì giá trị mới được dùng
    - Deps: T-16
    - NFR: giờ máy chủ trong câu trả lời ở múi giờ UTC theo đặc tả
    - Owner: cả team

#### S-09 — Trụ báo nhịp tim và thời điểm liên lạc cuối được cập nhật  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 1 · **Deps:** S-08 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn biết trụ còn liên lạc lần cuối lúc nào để phân biệt trụ đang rảnh với trụ đã chết
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ đang trực tuyến, Khi trụ gửi `Heartbeat`, Thì cột thời điểm liên lạc cuối đổi và hệ thống trả về giờ hiện tại của máy chủ
  - Giả sử trụ gửi bất kỳ tin nhắn nào khác, Khi hệ thống nhận, Thì thời điểm liên lạc cuối cũng được cập nhật, không chỉ với `Heartbeat`
  - Giả sử đồng hồ của trụ lệch nhiều giờ, Khi trụ gửi `Heartbeat`, Thì hệ thống vẫn ghi theo giờ máy chủ, không theo giờ trụ
- **NFR / ràng buộc kỹ thuật:** chỉ cập nhật một cột, không đọc-sửa-ghi cả bản ghi vì 50 trụ gửi đồng thời

  **Task kỹ thuật của S-09:**

  - **T-18 — Handler `Heartbeat` cập nhật một cột `last_seen_at` và trả giờ máy chủ** *(Sprint 2, Todo)*
    - Mô tả: Handler theo mẫu T-16. Cập nhật `charge_points.last_seen_at` bằng một câu `UPDATE` đúng một cột. Gọi cùng hàm cập nhật đó từ khung ở T-14 cho mọi tin nhắn tới.
    - AC: Trụ ảo gửi nhịp tim thì `last_seen_at` đổi; gửi `StatusNotification` cũng làm cột này đổi
    - Deps: T-17
    - NFR: không khoá bản ghi lâu hơn một câu lệnh
    - Owner: cả team
  - **T-19 — Test nhịp tim với trụ ảo đặt sai giờ hệ thống** *(Sprint 2, Todo)*
    - Mô tả: Chạy trụ ảo trong container có biến môi trường múi giờ lệch, gửi nhịp tim, kiểm `last_seen_at` ghi theo giờ máy chủ cơ sở dữ liệu. Đây là bằng chứng cho AC thứ ba của S-09 và là chỗ team học vì sao phải so thời gian ở một nơi.
    - AC: `last_seen_at` chênh với `now()` của cơ sở dữ liệu dưới 2 giây dù trụ ảo báo giờ lệch 5 tiếng
    - Deps: T-18
    - NFR: test chạy được trong CI
    - Owner: cả team

#### S-10 — Trụ báo trạng thái từng đầu nối qua `StatusNotification`  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-09 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn biết ngay khi một đầu nối chuyển sang bận, rảnh hay lỗi để không phải ra tận trạm mới biết trụ hỏng
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ gửi `StatusNotification` báo đầu nối số 1 chuyển sang `Charging`, Khi hệ thống nhận, Thì trạng thái đầu nối đó đổi trong bảng `connectors`
  - Giả sử trụ báo đầu nối lỗi kèm `errorCode` và `vendorErrorCode`, Khi hệ thống nhận, Thì lưu mã lỗi và thời điểm để tra cứu sau
  - Giả sử trụ gửi trạng thái cho `connectorId` 0, Khi hệ thống nhận, Thì hiểu là trạng thái của cả trụ, không phải một đầu nối
  - Giả sử trụ gửi trạng thái cho đầu nối không tồn tại trong khai báo, Khi hệ thống nhận, Thì ghi cảnh báo và bỏ qua, không tạo đầu nối mới
- **NFR / ràng buộc kỹ thuật:** cập nhật trạng thái không được khoá bảng lâu, vì 50 trụ gửi đồng thời

  **Task kỹ thuật của S-10:**

  - **T-20 — Ánh xạ trạng thái OCPP sang trạng thái nội bộ của bảng `connectors`** *(Sprint 2, Todo)*
    - Mô tả: Bảng ánh xạ 9 trạng thái của đặc tả (`Available`, `Preparing`, `Charging`, `SuspendedEV`, `SuspendedEVSE`, `Finishing`, `Reserved`, `Unavailable`, `Faulted`) sang bốn trạng thái nội bộ: rảnh, bận, đặt chỗ, lỗi. Đặt bảng ánh xạ ở một module riêng để màn hình và báo cáo dùng chung. Handler theo mẫu T-16.
    - AC: Đổi trạng thái trên trụ ảo thì bảng `connectors` đổi theo trong vòng 1 giây; trạng thái lạ chưa biết lưu nguyên văn vào cột riêng
    - Deps: T-19
    - NFR: trạng thái lạ không làm sập luồng xử lý
    - Owner: cả team
  - **T-21 — Lưu mã lỗi và thời điểm vào bảng `connector_errors`** *(Sprint 2, Todo)*
    - Mô tả: Bảng mới `connector_errors` chỉ ghi thêm: đầu nối, mã lỗi, mã lỗi nhà sản xuất, thời điểm. Ghi mỗi khi `errorCode` khác `NoError`. Migration theo mẫu T-10.
    - AC: Trụ ảo báo `Faulted` kèm mã lỗi thì có một dòng mới; báo `Available` sau đó không xoá dòng cũ
    - Deps: T-20
    - NFR: có chỉ mục theo đầu nối và thời điểm để S-46 đếm lỗi theo khoảng thời gian
    - Owner: cả team
  - **T-22 — Bỏ qua đầu nối chưa khai báo kèm cảnh báo, không tạo mới** *(Sprint 2, Todo)*
    - Mô tả: Nhánh lỗi của T-20: `connectorId` lớn hơn số đầu nối đã khai ở S-05 thì ghi cảnh báo kèm mã trụ và số đầu nối, trả `CALLRESULT` rỗng theo đặc tả, không chèn bản ghi.
    - AC: Trụ ảo khai 2 đầu nối gửi trạng thái cho đầu nối 3 thì bảng `connectors` vẫn 2 dòng và log có cảnh báo
    - Deps: T-21
    - NFR: cảnh báo gom theo trụ, không lặp mỗi giây
    - Owner: cả team

#### S-11 — Vận hành viên xem trạng thái mọi trụ trên một màn hình tự cập nhật  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 3 · **Deps:** S-10 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn thấy toàn bộ trạm và trụ cùng trạng thái trên một màn hình để phát hiện trụ hỏng mà không phải bấm vào từng cái
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử có 20 trụ đang kết nối, Khi mở màn hình theo dõi, Thì thấy đủ 20 trụ kèm trạng thái từng đầu nối, tải xong dưới 2 giây
  - Giả sử một đầu nối đổi trạng thái, Khi tôi đang mở màn hình, Thì trạng thái trên màn hình đổi theo trong 1 giây mà tôi không cần tải lại trang
  - Giả sử một trụ đang ngoại tuyến, Khi xem màn hình, Thì trụ đó hiện rõ là ngoại tuyến kèm thời điểm liên lạc cuối
  - Giả sử tôi là chủ trạm chứ không phải vận hành viên, Khi mở màn hình, Thì chỉ thấy trụ thuộc trạm của mình
  - Giả sử kết nối đẩy dữ liệu bị đứt, Khi trình duyệt phát hiện, Thì tự nối lại và tải lại trạng thái đầy đủ
- **NFR / ràng buộc kỹ thuật:** lấy trạng thái toàn mạng lưới trong một truy vấn, không gọi một lần cho mỗi trụ

  **Task kỹ thuật của S-11:**

  - **T-23 — Truy vấn một lần trả về cây trạm–trụ–đầu nối đã lọc theo quyền** *(Sprint 2, Todo)*
    - Mô tả: Một truy vấn nối ba bảng, trả về cây ba tầng, đi qua hàm lọc sở hữu ở T-07. Đo thời gian chạy với 50 trụ và 200 đầu nối bằng dữ liệu seed trước khi coi là xong.
    - AC: Trả về đúng cây ba tầng; chạy dưới 200ms với 50 trụ; chủ trạm chỉ nhận trạm của mình
    - Deps: T-22
    - NFR: không dùng vòng lặp gọi truy vấn con cho từng trụ
    - Owner: cả team
  - **T-24 — Màn hình theo dõi dạng lưới, mỗi ô một trụ, nhãn chữ kèm màu** *(Sprint 2, Todo)*
    - Mô tả: Lưới trạm → trụ → đầu nối. Trạng thái phân biệt bằng nhãn chữ kèm màu, không chỉ màu. Trụ ngoại tuyến hiện thời điểm liên lạc cuối. Bố cục trang theo T-09.
    - AC: 20 trụ hiện đủ trên một màn hình máy tính không cần cuộn ngang; người mù màu vẫn đọc được trạng thái
    - Deps: T-23
    - NFR: trạng thái phân biệt không chỉ bằng màu, thêm nhãn chữ
    - Owner: cả team
  - **T-25 — Kênh đẩy trạng thái xuống trình duyệt khi đầu nối đổi** *(Sprint 2, Todo)*
    - Mô tả: Khi T-20 đổi trạng thái đầu nối, phát một sự kiện nội bộ; một endpoint Server-Sent Events đẩy sự kiện đó xuống các trình duyệt đang mở màn hình, đã lọc theo quyền. Trình duyệt tự nối lại khi đứt và gọi lại truy vấn T-23.
    - AC: Đổi trạng thái trên trụ ảo thì màn hình đổi trong 1 giây; tắt rồi bật lại máy chủ thì màn hình tự khôi phục không cần tải lại
    - Deps: T-24
    - NFR: không đẩy sự kiện của trạm này tới trình duyệt của chủ trạm khác
    - Owner: cả team

#### S-12 — Trụ quá hạn nhịp tim bị đánh dấu ngoại tuyến  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-09 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn trụ không còn liên lạc tự chuyển sang ngoại tuyến để màn hình không hiện "rảnh" cho một trụ đã mất điện
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ không gửi tin nhắn nào quá hai lần khoảng nhịp tim đã hẹn, Khi job kiểm tra chạy, Thì trụ chuyển sang ngoại tuyến và mọi đầu nối của nó hiện trạng thái không rõ
  - Giả sử trụ ngoại tuyến gửi lại nhịp tim, Khi hệ thống nhận, Thì trụ trở lại trực tuyến và đầu nối chờ `StatusNotification` kế tiếp để có trạng thái thật
  - Giả sử job kiểm tra không chạy vì tiến trình vừa khởi động lại, Khi mở màn hình, Thì trạng thái ngoại tuyến vẫn đúng vì suy từ thời điểm liên lạc cuối
- **NFR / ràng buộc kỹ thuật:** trạng thái ngoại tuyến phải suy ra từ thời điểm liên lạc cuối, không phụ thuộc việc tiến trình kiểm tra có đang chạy hay không

  **Task kỹ thuật của S-12:**

  - **T-26 — Job nền quét `last_seen_at` quá hai chu kỳ và đổi trạng thái** *(Sprint 2, Todo)*
    - Mô tả: Job chạy mỗi phút, so `last_seen_at` với `now()` của cơ sở dữ liệu, đổi trạng thái trụ quá hạn. Chạy lặp nhiều lần không gây tác dụng phụ. Đây là job nền đầu tiên của dự án — cách đăng ký và ghi log của nó là mẫu cho T-31, T-53.
    - AC: Dừng trụ ảo thì sau hai chu kỳ nhịp tim trụ chuyển sang ngoại tuyến; chạy job hai lần liên tiếp không đổi gì thêm
    - Deps: T-25
    - NFR: truy vấn xác định ngoại tuyến so sánh thời gian ở máy chủ cơ sở dữ liệu
    - Owner: cả team
  - **T-27 — Test dừng trụ ảo rồi bật lại, trạng thái đi đúng hai chiều** *(Sprint 2, Todo)*
    - Mô tả: Kịch bản tự động: bật trụ ảo, chờ trực tuyến, dừng container, chờ quá hai chu kỳ, kiểm ngoại tuyến, bật lại, kiểm trực tuyến và đầu nối có trạng thái thật sau `StatusNotification`.
    - AC: Kịch bản chạy xanh ba lần liên tiếp trên staging
    - Deps: T-26
    - NFR: khoảng nhịp tim trong test đặt ngắn (5 giây) để test không kéo dài
    - Owner: cả team

#### S-13 — Cùng mã trụ mở hai kết nối thì kết nối cũ bị đóng  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 1 · **Deps:** S-06 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn một trụ chỉ có đúng một kết nối sống để tin nhắn không bị xử lý hai lần khi trụ tự nối lại sau khi rớt mạng
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ đã có kết nối đang mở, Khi cùng mã đó mở kết nối thứ hai, Thì kết nối cũ bị đóng và kết nối mới được dùng
  - Giả sử kết nối cũ đã chết nhưng máy chủ chưa phát hiện, Khi kết nối mới tới, Thì kết nối mới vẫn được chấp nhận ngay, không chờ hết thời gian chờ
  - Giả sử kết nối mới tới đúng lúc kết nối cũ đang xử lý dở một tin nhắn, Khi xử lý xong, Thì câu trả lời không bị gửi vào kết nối mới
- **NFR / ràng buộc kỹ thuật:** bảng kết nối đang mở sống trong bộ nhớ tiến trình là chấp nhận được vì chỉ chạy một tiến trình; ghi rõ giới hạn này trong README

  **Task kỹ thuật của S-13:**

  - **T-28 — Bảng kết nối đang mở trong bộ nhớ, thay thế khi trùng mã** *(Sprint 2, Todo)*
    - Mô tả: Một cấu trúc ánh xạ mã trụ → kết nối đang mở, gắn vào T-12. Kết nối mới cùng mã thì đóng cái cũ trước rồi thay thế. Mọi lệnh máy chủ gửi xuống trụ (T-34, T-49) tra ở đây.
    - AC: Mở hai trụ ảo cùng mã thì kết nối đầu nhận khung đóng và bảng chỉ còn một mục
    - Deps: T-13
    - NFR: thao tác thay thế phải nguyên tử trong tiến trình
    - Owner: cả team
  - **T-29 — Test mở hai trụ ảo cùng mã, kết nối đầu nhận khung đóng** *(Sprint 2, Todo)*
    - Mô tả: Test tích hợp theo mẫu T-27: hai simulator cùng mã nối liên tiếp, kiểm kết nối đầu bị đóng với mã đóng chuẩn và tin nhắn của kết nối hai vẫn được xử lý.
    - AC: Test xanh trong CI; log ghi rõ kết nối nào bị thay
    - Deps: T-28
    - NFR: test không phụ thuộc thứ tự chạy với test khác
    - Owner: cả team

#### S-14 — Tin nhắn trùng mã nhận lại đúng câu trả lời cũ, không xử lý hai lần  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-08 · **Owner:** cả team
- **User story:** Là kế toán đối soát tôi muốn một tin nhắn trụ gửi lại vì mất mạng chỉ được xử lý một lần để phiên sạc và số đo không bị nhân đôi
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ gửi lại cùng một tin nhắn với cùng mã tin nhắn, Khi hệ thống nhận lần thứ hai, Thì trả về đúng câu trả lời cũ và không chạy lại handler
  - Giả sử tiến trình khởi động lại giữa hai lần gửi, Khi lần thứ hai tới, Thì vẫn nhận ra là trùng vì mã được lưu ở cơ sở dữ liệu
  - Giả sử hai tin nhắn khác nội dung nhưng trùng mã, Khi hệ thống nhận, Thì trả về câu trả lời của tin đầu và ghi cảnh báo
  - Giả sử bản ghi mã tin nhắn đã quá 7 ngày, Khi job dọn chạy, Thì bản ghi bị xoá và bảng không phình vô hạn
- **NFR / ràng buộc kỹ thuật:** chống trùng dựa trên khoá lưu ở cơ sở dữ liệu, không dựa vào biến trong bộ nhớ tiến trình

  **Task kỹ thuật của S-14:**

  - **T-30 — Bảng `ocpp_messages` lưu mã tin nhắn và câu trả lời đã gửi** *(Sprint 2, Todo)*
    - Mô tả: Bảng `ocpp_messages` khoá theo cặp (mã trụ, mã tin nhắn), lưu tên hành động, câu trả lời đã gửi, thời điểm. Chèn vào khung ở T-14 một bước tra bảng trước khi gọi handler. Migration theo mẫu T-10.
    - AC: Gửi lại cùng tin nhắn 5 lần thì chỉ có một bản ghi phiên và năm lần đều nhận cùng câu trả lời
    - Deps: T-17
    - NFR: tra bảng và gọi handler nằm trong cùng một giao dịch để hai tin tới đồng thời không cùng lọt
    - Owner: cả team
  - **T-31 — Job dọn bản ghi cũ hơn 7 ngày và test gửi lại 5 lần** *(Sprint 2, Todo)*
    - Mô tả: Job nền theo mẫu T-26 xoá bản ghi `ocpp_messages` quá 7 ngày. Test tích hợp theo mẫu T-29 cho ca gửi lại 5 lần và ca khởi động lại tiến trình giữa hai lần gửi.
    - AC: Sau khi job chạy, không còn bản ghi quá 7 ngày; hai test xanh trong CI
    - Deps: T-30
    - NFR: số ngày giữ là tham số cấu hình
    - Owner: cả team

#### S-15 — Trụ xác thực thẻ tài xế qua `Authorize`  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-08 · **Owner:** cả team
- **User story:** Là chủ trạm tôi muốn trụ chỉ cho sạc khi thẻ của tài xế hợp lệ để người không có tài khoản không sạc chùa được
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử thẻ đã gắn với một tài xế đang hoạt động, Khi trụ gửi `Authorize` với mã thẻ đó, Thì trả về `Accepted`
  - Giả sử thẻ bị khoá, Khi trụ gửi `Authorize`, Thì trả về `Blocked`
  - Giả sử thẻ đã quá hạn dùng, Khi trụ gửi `Authorize`, Thì trả về `Expired`
  - Giả sử mã thẻ không có trong hệ thống, Khi trụ gửi `Authorize`, Thì trả về `Invalid` và ghi nhật ký lần thử
  - Giả sử trụ thuộc trạm tạm ngừng, Khi trụ gửi `Authorize` với thẻ hợp lệ, Thì trả về `Blocked`
- **NFR / ràng buộc kỹ thuật:** mã thẻ là dữ liệu định danh — không ghi nguyên văn vào log, chỉ ghi bốn ký tự cuối

  **Task kỹ thuật của S-15:**

  - **T-32 — Bảng `id_tags` gắn thẻ với tài xế, có trạng thái khoá và hạn dùng** *(Sprint 2, Todo)*
    - Mô tả: Bảng `id_tags`: mã thẻ unique, khoá ngoại tới `users` vai trò tài xế, trạng thái, hạn dùng. Seed mỗi tài xế thử nghiệm một thẻ. Migration theo mẫu T-10.
    - AC: Migration tiến và lùi được; chèn hai thẻ cùng mã thì bị từ chối
    - Deps: T-04
    - NFR: có chỉ mục theo mã thẻ vì mọi `Authorize` tra theo cột này
    - Owner: cả team
  - **T-33 — Handler `Authorize` trả về `Accepted`, `Blocked`, `Expired` hoặc `Invalid`** *(Sprint 2, Todo)*
    - Mô tả: Handler theo mẫu T-16, tra bảng T-32 và trạng thái trạm, trả `idTagInfo` đúng cấu trúc đặc tả. Test theo bảng dữ liệu như T-15 cho năm ca của AC.
    - AC: Năm ca của S-15 đều đúng trên trụ ảo; log chỉ hiện bốn ký tự cuối của thẻ
    - Deps: T-32
    - NFR: không tiết lộ lý do chi tiết ngoài bốn trạng thái chuẩn
    - Owner: cả team

#### S-16 — Vận hành viên khởi động lại trụ từ xa bằng `Reset`  *[Story, Sprint 2]*

- **Tier/Priority/Status:** Ready / Should / Todo
- **SP:** 1 · **Deps:** S-11 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn khởi động lại một trụ đang treo từ màn hình theo dõi để không phải cử người ra tận trạm rút điện
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ đang trực tuyến, Khi tôi bấm khởi động lại và chọn kiểu mềm, Thì hệ thống gửi `Reset` và hiện xác nhận `Accepted` từ trụ trong 5 giây
  - Giả sử trụ đang ngoại tuyến, Khi tôi bấm khởi động lại, Thì nhận thông báo trụ đang ngoại tuyến ngay, không treo chờ
  - Giả sử trụ không trả lời trong 30 giây, Khi hết thời gian chờ, Thì hiện lỗi hết thời gian và lời gọi bị huỷ
- **NFR / ràng buộc kỹ thuật:** đây là lệnh đầu tiên đi từ máy chủ xuống trụ — cơ chế chờ câu trả lời phải viết chung để S-23, S-24 dùng lại

  **Task kỹ thuật của S-16:**

  - **T-34 — Gửi `CALL` từ máy chủ tới trụ và khớp `CALLRESULT` theo mã tin nhắn** *(Sprint 2, Todo)*
    - Mô tả: Hàm dùng chung: sinh mã tin nhắn duy nhất, ghi khung `CALL` bằng T-14, gửi qua kết nối tra ở T-28, chờ `CALLRESULT` có cùng mã với thời gian chờ cấu hình được. Dùng cho `Reset` trước, sau này cho mọi lệnh khác.
    - AC: Gọi `Reset` trên trụ ảo nhận đúng `CALLRESULT`; trụ không trả lời thì hàm trả lỗi hết thời gian sau đúng số giây cấu hình
    - Deps: T-28
    - NFR: một lời gọi đang chờ không chặn việc xử lý tin nhắn khác trên cùng kết nối
    - Owner: cả team
  - **T-35 — Nút khởi động lại trên màn hình theo dõi, báo lỗi khi trụ ngoại tuyến** *(Sprint 2, Todo)*
    - Mô tả: Nút trên ô trụ ở T-24, hộp chọn kiểu mềm/cứng, gọi API dùng T-34. Trụ ngoại tuyến thì API trả lỗi ngay không gọi xuống trụ. Ghi một dòng nhật ký thao tác — bảng nhật ký sẽ chuẩn hoá ở T-57, tạm ghi log ứng dụng.
    - AC: Bấm nút trên trụ ảo trực tuyến thì trụ khởi động lại và ô trụ chuyển ngoại tuyến rồi trực tuyến; trụ ngoại tuyến thì hiện thông báo ngay
    - Deps: T-34
    - NFR: chỉ vai trò vận hành viên và quản trị thấy nút này
    - Owner: cả team

#### S-17 — Phiên sạc bắt đầu khi trụ gửi `StartTransaction`  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-15, S-14 · **Owner:** cả team
- **User story:** Là tài xế tôi muốn quẹt thẻ và cắm súng là phiên sạc bắt đầu để không phải thao tác gì thêm ở trụ
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử thẻ hợp lệ và đầu nối rảnh, Khi trụ gửi `StartTransaction` kèm số đo đầu, Thì hệ thống tạo phiên ở trạng thái đang sạc, lưu số đo đầu và thời điểm, trả về `transactionId` do hệ thống cấp cùng `Accepted`
  - Giả sử thẻ bị khoá hoặc không tồn tại, Khi trụ gửi `StartTransaction`, Thì vẫn trả về `transactionId` nhưng `idTagInfo` là `Blocked`/`Invalid` theo đặc tả, và phiên được đánh dấu cần xem xét
  - Giả sử đầu nối đó đang có phiên chưa đóng, Khi trụ gửi `StartTransaction` mới, Thì phiên cũ bị đóng với lý do bất thường rồi phiên mới được tạo, và có cảnh báo
  - Giả sử trụ gửi lại `StartTransaction` cùng mã tin nhắn, Khi hệ thống nhận, Thì trả về cùng `transactionId` cũ theo S-14
- **NFR / ràng buộc kỹ thuật:** `transactionId` là số nguyên tăng dần do cơ sở dữ liệu cấp, không dùng thời gian

  **Task kỹ thuật của S-17:**

  - **T-36 — Bảng `charging_sessions` kèm migration, mã phiên do hệ thống cấp** *(Sprint 3, Todo)*
    - Mô tả: Bảng `charging_sessions`: khoá chính tự tăng làm `transactionId`, đầu nối, thẻ, tài xế, số đo đầu/cuối, thời điểm bắt đầu/kết thúc, trạng thái, lý do dừng. Migration theo mẫu T-10. Đây là bảng trung tâm — mọi story từ E-05 trở đi đọc nó.
    - AC: Migration tiến và lùi được; hai phiên không thể cùng mở trên một đầu nối nhờ chỉ mục unique có điều kiện
    - Deps: T-32
    - NFR: trạng thái phiên là enum rõ ràng: đang sạc, đã kết thúc, bất thường, cần xem xét
    - Owner: cả team
  - **T-37 — Handler `StartTransaction` kiểm thẻ, tạo phiên, trả `transactionId`** *(Sprint 3, Todo)*
    - Mô tả: Handler theo mẫu T-16, dùng lại hàm kiểm thẻ của T-33, chèn phiên vào T-36, xử lý ca đầu nối còn phiên mở. Đối chiếu trường của tin nhắn với bản ghi K-01.
    - AC: Trụ ảo bắt đầu phiên thì bảng có dòng mới với số đo đầu đúng bằng giá trị trụ gửi; bốn ca của S-17 đều xanh
    - Deps: T-36
    - NFR: toàn bộ xử lý nằm trong một giao dịch cơ sở dữ liệu
    - Owner: cả team

#### S-18 — Phiên sạc kết thúc khi trụ gửi `StopTransaction` và chốt số kWh  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-17 · **Owner:** cả team
- **User story:** Là tài xế tôi muốn rút súng là phiên kết thúc và số điện được chốt để tôi biết mình đã sạc bao nhiêu
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên đang sạc, Khi trụ gửi `StopTransaction` kèm số đo cuối và lý do, Thì phiên chuyển sang đã kết thúc, lưu số đo cuối, thời điểm và lý do, số kWh bằng hiệu số đo cuối trừ số đo đầu chia 1000
  - Giả sử số đo cuối nhỏ hơn số đo đầu, Khi hệ thống nhận, Thì phiên được đánh dấu cần xem xét với số kWh để trống, không ghi số âm
  - Giả sử `StopTransaction` mang `transactionId` không tồn tại, Khi hệ thống nhận, Thì trả về `CALLRESULT` theo đặc tả nhưng ghi cảnh báo và lưu tin nhắn vào bảng chờ đối chiếu
  - Giả sử `StopTransaction` kèm danh sách số đo trong `transactionData`, Khi hệ thống nhận, Thì các số đo đó được lưu như `MeterValues`
- **NFR / ràng buộc kỹ thuật:** số kWh của phiên tính bằng hiệu số đo cuối trừ số đo đầu, không cộng dồn từng lần báo

  **Task kỹ thuật của S-18:**

  - **T-38 — Handler `StopTransaction` đóng phiên, lưu lý do dừng** *(Sprint 3, Todo)*
    - Mô tả: Handler theo mẫu T-37. Tra phiên theo `transactionId`, cập nhật số đo cuối, thời điểm, lý do (`Local`, `Remote`, `EVDisconnected`, `PowerLoss`…), trạng thái. Ca `transactionId` lạ ghi vào bảng `orphan_messages`.
    - AC: Trụ ảo dừng phiên thì dòng phiên có đủ số đo cuối và lý do; `transactionId` bịa thì có dòng trong `orphan_messages`
    - Deps: T-37
    - NFR: phiên đã kết thúc nhận `StopTransaction` lần nữa thì không đổi gì
    - Owner: cả team
  - **T-39 — Tính kWh bằng hiệu số đo cuối trừ số đo đầu, test với ba phiên mẫu** *(Sprint 3, Todo)*
    - Mô tả: Hàm thuần tính kWh từ hai số đo Wh, xử lý ca số đo lùi. Test theo bảng dữ liệu với ba phiên mẫu tính tay: phiên thường, phiên số đo cuối nhỏ hơn số đo đầu, phiên số đo bằng nhau. Đặt hàm ở module riêng để E-05 dùng lại.
    - AC: Ba ca đều ra đúng đáp án tính tay; ca lùi trả về không có giá trị thay vì số âm
    - Deps: T-38
    - NFR: không làm tròn ở bước này — làm tròn chỉ xảy ra khi tính tiền
    - Owner: cả team

#### S-19 — Số đo điện năng được ghi liên tục qua `MeterValues`  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-18 · **Owner:** cả team
- **User story:** Là tài xế tôi muốn thấy số điện đã nạp tăng dần trong lúc sạc để biết khi nào đủ để đi tiếp
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên đang sạc, Khi trụ gửi `MeterValues` có đại lượng `Energy.Active.Import.Register`, Thì giá trị và mốc thời gian được lưu gắn với phiên
  - Giả sử `MeterValues` kèm nhiều đại lượng khác như dòng điện, công suất, Khi hệ thống nhận, Thì chỉ lưu các đại lượng đã biết, bỏ qua phần còn lại không báo lỗi
  - Giả sử `MeterValues` tới cho đầu nối không có phiên đang chạy, Khi hệ thống nhận, Thì lưu vào bảng chờ đối chiếu và không tạo phiên
  - Giả sử trụ gửi số đo mỗi 10 giây cho 20 trụ, Khi hệ thống ghi, Thì thời gian trả lời trụ vẫn dưới 200ms
- **NFR / ràng buộc kỹ thuật:** lưu số đo không được làm chậm việc trả lời trụ

  **Task kỹ thuật của S-19:**

  - **T-40 — Bảng `meter_values` kèm migration và chỉ mục theo phiên** *(Sprint 3, Todo)*
    - Mô tả: Bảng `meter_values`: phiên, mốc thời gian, đại lượng, giá trị, đơn vị. Chỉ mục ghép (phiên, mốc thời gian). Migration theo mẫu T-36.
    - AC: Migration tiến và lùi được; truy vấn số đo mới nhất của một phiên dùng chỉ mục
    - Deps: T-36
    - NFR: đơn vị lưu nguyên văn từ tin nhắn (`Wh` hay `kWh`) để tính đúng khi đọc
    - Owner: cả team
  - **T-41 — Handler `MeterValues` đọc đúng đại lượng `Energy.Active.Import.Register`** *(Sprint 3, Todo)*
    - Mô tả: Handler theo mẫu T-37. Cấu trúc `meterValue[].sampledValue[]` lồng hai tầng — đối chiếu bản ghi K-01. Chỉ lưu `Energy.Active.Import.Register`, `Power.Active.Import`, `Current.Import`; đại lượng khác bỏ qua. Ghi qua một câu chèn hàng loạt.
    - AC: Trụ ảo gửi số đo mỗi 10 giây thì bảng có dòng mới đúng nhịp; số đo tới cho đầu nối rảnh nằm ở `orphan_messages`
    - Deps: T-40
    - NFR: trả lời trụ trước, ghi bảng chờ đối chiếu sau
    - Owner: cả team

#### S-20 — Số đo lùi hoặc trùng mốc thời gian bị bỏ qua  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 1 · **Deps:** S-19 · **Owner:** cả team
- **User story:** Là kế toán đối soát tôi muốn số đo của một phiên chỉ tăng theo thời gian để hoá đơn không bị tính lùi khi trụ gửi lại dữ liệu cũ
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử số đo mới có mốc thời gian cũ hơn số đo đã lưu của cùng phiên, Khi hệ thống nhận, Thì bỏ qua và ghi cảnh báo, không ghi đè số đo mới hơn
  - Giả sử số đo mới có mốc thời gian trùng và giá trị trùng với số đo đã lưu, Khi hệ thống nhận, Thì bỏ qua không cảnh báo
  - Giả sử số đo mới có mốc thời gian mới hơn nhưng giá trị nhỏ hơn số đo đã lưu, Khi hệ thống nhận, Thì lưu nhưng đánh dấu phiên cần xem xét
- **NFR / ràng buộc kỹ thuật:** so sánh theo mốc thời gian trong tin nhắn, không theo thời điểm máy chủ nhận được

  **Task kỹ thuật của S-20:**

  - **T-42 — So mốc thời gian với số đo mới nhất của phiên trước khi ghi** *(Sprint 3, Todo)*
    - Mô tả: Chèn vào T-41 một bước đọc số đo mới nhất của phiên (dùng chỉ mục T-40) và áp ba quy tắc của S-20. Quy tắc viết thành hàm thuần để test theo bảng.
    - AC: Ba quy tắc đều có test đơn vị xanh; chạy trên trụ ảo không làm chậm trả lời quá 200ms
    - Deps: T-41
    - NFR: đọc và ghi trong cùng giao dịch để hai số đo tới đồng thời không cùng lọt
    - Owner: cả team
  - **T-43 — Test gửi số đo lùi và số đo trùng, có cảnh báo trong log** *(Sprint 3, Todo)*
    - Mô tả: Test tích hợp theo mẫu T-29: dùng simulator hoặc gửi khung tay qua WebSocket ba số đo theo thứ tự mới → cũ → trùng. Kiểm bảng và log.
    - AC: Bảng chỉ có số đo mới; log có đúng một cảnh báo cho số đo lùi và không cảnh báo cho số đo trùng
    - Deps: T-42
    - NFR: test chạy trong CI
    - Owner: cả team

#### S-21 — Phiên đang dở được khôi phục đúng khi trụ nối lại  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 3 · **Deps:** S-20, S-13 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn phiên sạc không bị mất hay nhân đôi khi trụ rớt mạng giữa chừng để khách vẫn được tính đúng số điện đã sạc
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử trụ mất kết nối giữa lúc đang sạc, Khi trụ nối lại và gửi `StatusNotification` báo đầu nối vẫn `Charging`, Thì hệ thống giữ nguyên phiên đó thay vì tạo phiên mới
  - Giả sử trụ mất kết nối rồi phiên kết thúc ở phía trụ khi đang ngoại tuyến, Khi trụ nối lại và gửi `StopTransaction` tới muộn với đúng `transactionId`, Thì hệ thống vẫn ghi nhận và tính đúng số kWh
  - Giả sử trụ nối lại và gửi `MeterValues` dồn của khoảng thời gian mất mạng, Khi hệ thống nhận, Thì các số đo được lưu theo đúng mốc thời gian trong tin nhắn
  - Giả sử 20 trụ ảo bị ngắt–nối ngẫu nhiên nhiều lần trong phiên, Khi mọi phiên kết thúc, Thì không phiên nào bị mất, bị nhân đôi, hay sai số kWh
  - Giả sử trụ nối lại nhưng báo đầu nối đã `Available` mà hệ thống còn phiên mở, Khi hệ thống nhận, Thì phiên được đánh dấu cần xem xét chứ không tự đóng với số kWh đoán
- **NFR / ràng buộc kỹ thuật:** khớp phiên theo `transactionId` do hệ thống cấp, không khớp theo thời gian

  **Task kỹ thuật của S-21:**

  - **T-44 — Khớp phiên đang chạy theo `transactionId` khi trụ nối lại** *(Sprint 3, Todo)*
    - Mô tả: Khi trụ trở lại trực tuyến (T-26 chiều ngược), đọc phiên đang mở của từng đầu nối; `StatusNotification` `Charging` thì giữ, `Available` thì đánh dấu cần xem xét. Xem bản ghi K-01 để biết simulator báo gì sau khi nối lại.
    - AC: Ngắt trụ ảo giữa phiên rồi nối lại thì phiên cũ tiếp tục, không sinh phiên thứ hai
    - Deps: T-42
    - NFR: không đóng phiên tự động chỉ vì trụ ngoại tuyến
    - Owner: cả team
  - **T-45 — Xử lý `StopTransaction` tới muộn sau khi trụ đã ngoại tuyến** *(Sprint 3, Todo)*
    - Mô tả: Mở rộng T-38: phiên có trụ đang ngoại tuyến vẫn nhận `StopTransaction` khi trụ nối lại; `transactionData` dồn được lưu qua T-41 theo mốc thời gian trong tin nhắn.
    - AC: Dừng trụ ảo khi đang sạc, kết thúc phiên ở phía trụ, bật lại — phiên trong hệ thống đóng đúng với số kWh khớp số đo trụ
    - Deps: T-44
    - NFR: thời điểm kết thúc lấy từ tin nhắn, không lấy giờ máy chủ lúc nhận
    - Owner: cả team
  - **T-46 — Kịch bản 20 trụ ảo ngắt–nối ngẫu nhiên giữa phiên, kiểm kWh cuối** *(Sprint 3, Todo)*
    - Mô tả: Kịch bản tự động: bật 20 trụ ảo, mỗi trụ chạy một phiên, ngắt–nối ngẫu nhiên 1–3 lần mỗi phiên, cuối cùng so số kWh trong hệ thống với số đo simulator báo. In bảng đối chiếu. Đây là bằng chứng cho AC của S-21 và E-04, và là kịch bản T-56 đưa vào CI.
    - AC: Chạy trên staging thì 20/20 phiên khớp; chạy lại ba lần vẫn đúng
    - Deps: T-45
    - NFR: kịch bản có tham số số trụ và số lần ngắt để chạy nhanh trong CI
    - Owner: cả team

#### S-23 — Vận hành viên dừng phiên sạc từ xa bằng `RemoteStopTransaction`  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-18, S-16 · **Owner:** cả team
- **User story:** Là vận hành viên tôi muốn dừng một phiên sạc từ xa để xử lý khi trụ có sự cố hoặc khách bỏ xe quá lâu
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên đang sạc và trụ trực tuyến, Khi tôi bấm dừng, Thì hệ thống gửi `RemoteStopTransaction`, trụ trả `Accepted`, và phiên chỉ được đóng khi trụ gửi `StopTransaction` thật với lý do `Remote`
  - Giả sử trụ trả `Rejected`, Khi hệ thống nhận, Thì phiên vẫn đang sạc và tôi thấy thông báo trụ từ chối
  - Giả sử trụ ngoại tuyến, Khi tôi bấm dừng, Thì báo lỗi ngay chứ không treo, và phiên không đổi trạng thái
  - Giả sử trụ trả `Accepted` nhưng không gửi `StopTransaction` trong 2 phút, Khi hết thời gian, Thì phiên được đánh dấu cần xem xét
- **NFR / ràng buộc kỹ thuật:** phiên dừng bằng lệnh vẫn chốt tiền như phiên dừng bình thường

  **Task kỹ thuật của S-23:**

  - **T-49 — Gửi `RemoteStopTransaction` và chờ trụ gửi `StopTransaction` thật** *(Sprint 3, Todo)*
    - Mô tả: API dừng phiên dùng hàm gửi lệnh T-34, truyền `transactionId`. Không tự đóng phiên khi nhận `Accepted`; đặt một mốc chờ 2 phút, quá mốc thì đánh dấu cần xem xét qua job T-53.
    - AC: Dừng phiên trên trụ ảo thì phiên đóng với lý do `Remote` và số kWh đúng; trụ ảo cấu hình từ chối thì phiên vẫn chạy
    - Deps: T-38, T-34
    - NFR: lệnh dừng ghi nhật ký kèm người thực hiện qua hàm ở T-57
    - Owner: cả team
  - **T-50 — Nút dừng trên màn hình phiên, hết thời gian chờ thì báo lỗi rõ** *(Sprint 3, Todo)*
    - Mô tả: Nút trên màn hình phiên đang chạy (dùng lại màn hình T-48 với quyền vận hành viên), trạng thái chờ có đồng hồ, ba thông báo khác nhau cho từ chối, ngoại tuyến, hết thời gian.
    - AC: Ba ca lỗi của S-23 hiện đúng ba thông báo khác nhau; ca thành công thấy phiên chuyển sang đã kết thúc không cần tải lại
    - Deps: T-49
    - NFR: chỉ vai trò vận hành viên và quản trị thấy nút này
    - Owner: cả team

#### S-25 — Phiên không có tin kết thúc quá lâu bị đánh dấu bất thường  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 1 · **Deps:** S-21 · **Owner:** cả team
- **User story:** Là kế toán đối soát tôi muốn phiên treo được lôi ra danh sách riêng để không có phiên nào âm thầm chạy mãi và không bao giờ được tính tiền
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên đang sạc mà trụ ngoại tuyến quá ngưỡng cấu hình, Khi job kiểm tra chạy, Thì phiên chuyển sang bất thường và hiện trong danh sách phiên bất thường
  - Giả sử phiên bất thường sau đó nhận `StopTransaction` muộn, Khi hệ thống nhận, Thì phiên đóng bình thường và rời khỏi danh sách
  - Giả sử vận hành viên đóng tay một phiên bất thường, Khi lưu, Thì phải nhập lý do và số kWh lấy theo số đo cuối cùng đã có
- **NFR / ràng buộc kỹ thuật:** ngưỡng thời gian là tham số cấu hình, mặc định 6 giờ

  **Task kỹ thuật của S-25:**

  - **T-53 — Job quét phiên đang chạy mà trụ ngoại tuyến quá ngưỡng cấu hình** *(Sprint 3, Todo)*
    - Mô tả: Job nền theo mẫu T-26: tìm phiên đang sạc có trụ ngoại tuyến lâu hơn ngưỡng, hoặc phiên chờ `StopTransaction` sau lệnh dừng quá 2 phút (T-49), đổi sang bất thường.
    - AC: Dừng trụ ảo giữa phiên, chỉnh ngưỡng xuống 1 phút, sau 2 phút phiên hiện trong danh sách bất thường
    - Deps: T-46
    - NFR: job không đóng phiên, chỉ đánh dấu — đóng là quyết định của người
    - Owner: cả team
  - **T-54 — Danh sách phiên bất thường trên màn hình vận hành** *(Sprint 3, Todo)*
    - Mô tả: Trang danh sách phiên bất thường với nút đóng tay yêu cầu lý do. Bố cục theo T-24; đóng tay ghi nhật ký qua hàm T-57.
    - AC: Phiên bất thường hiện đủ mã, trụ, thời điểm mất liên lạc, số đo cuối; đóng tay không có lý do thì bị chặn
    - Deps: T-53
    - NFR: chỉ vai trò vận hành viên và kế toán vào được trang này
    - Owner: cả team

#### S-60 — Vận hành viên đổi cấu hình trụ từ xa bằng `ChangeConfiguration`  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-16 · **Owner:** chưa phân
- **User story:** Là vận hành viên tôi muốn đổi khoảng nhịp tim và chu kỳ gửi số đo của trụ từ xa để không phải ra trạm mỗi khi muốn trụ báo dày hơn hay thưa hơn
- **Acceptance Criteria (Given/When/Then):**
  - Đổi được `HeartbeatInterval` và `MeterValueSampleInterval` qua `ChangeConfiguration`, trụ trả `Accepted`, và có thể đọc lại bằng `GetConfiguration` để đối chiếu. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt danh sách khoá cấu hình được phép đổi; trụ trả `RebootRequired` thì phải hỏi người dùng có khởi động lại không

### E-05 — Biểu giá và tính tiền

**Tier:** Next · **Priority:** Must · **Status:** Todo · **Deps:** E-04 · **Owner:** chưa phân

**Mô tả:** Phần khó âm thầm nhất của dự án. Một phiên sạc kéo dài có thể cắt qua nhiều khung giờ với đơn giá khác nhau, cộng thêm phí chiếm trụ tính theo phút sau khi sạc xong mà xe chưa rút. Tiền phải đúng tới từng đồng và giải thích được từng đoạn. Sprint 4 làm trọn: khai báo biểu giá, chia đoạn, hoá đơn.

**Acceptance (mức epic):** Bộ ca kiểm thử có đáp án tính tay đều khớp, gồm cả phiên cắt qua ranh giới khung giờ, phiên qua nửa đêm và phiên có phí chiếm trụ

**NFR:** làm tròn tiền theo quy tắc thống nhất, khai báo rõ ở một chỗ duy nhất

#### S-28 — Chủ trạm khai báo biểu giá theo kWh và phí chiếm trụ theo phút  *[Story, Sprint 4]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 3 · **Deps:** S-18, S-04 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn đặt giá điện theo kWh và phí chiếm trụ theo phút cho trạm của mình để khách trả đúng phần điện đã dùng và không bỏ xe chiếm trụ sau khi sạc xong
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tôi là chủ trạm, Khi khai báo đơn giá theo kWh và phí theo phút kèm thời gian ân hạn, Thì biểu giá được lưu và gắn với trạm
  - Giả sử phiên đã sạc xong mà trụ báo đầu nối `Finishing` hoặc `SuspendedEV` quá thời gian ân hạn, Khi tính tiền, Thì phí chiếm trụ được tính từ hết ân hạn tới lúc rút súng
  - Giả sử đơn giá âm hoặc thời gian ân hạn âm, Khi lưu, Thì bị chặn ngay tại ô nhập
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** tiền lưu bằng số nguyên đồng, không dùng số thực

#### S-29 — Biểu giá có nhiều khung giờ trong ngày, không chồng lấn và phủ kín 24 giờ  *[Story, Sprint 4]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 3 · **Deps:** S-28 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn đặt đơn giá khác nhau theo khung giờ cao điểm và thấp điểm để khuyến khích khách sạc ban đêm
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tôi khai ba khung giờ 00:00–06:00, 06:00–22:00, 22:00–24:00 với ba đơn giá, Khi lưu, Thì biểu giá được chấp nhận
  - Giả sử hai khung giờ chồng lấn hoặc còn khoảng trống trong ngày, Khi lưu, Thì bị chặn kèm chỉ rõ khoảng nào bị chồng hoặc hở
  - Giả sử một khung giờ bắt đầu sau nửa đêm của ngày hôm trước như 22:00–02:00, Khi lưu, Thì được tách thành hai đoạn nội bộ để mọi khung đều nằm trong một ngày
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** kiểm phủ kín 24 giờ ở máy chủ, không tin giao diện

#### S-30 — Phiên cắt qua nhiều khung giờ được chia đoạn và tính đúng từng đoạn  *[Story, Sprint 4]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 5 · **Deps:** S-29, S-19 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn tiền được tính đúng theo giờ tôi thực sự sạc để không bị tính giá cao điểm cho phần sạc ban đêm
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên bắt đầu 21:30 và kết thúc 23:30 với khung giá đổi lúc 22:00, Khi tính tiền, Thì phiên được chia thành hai đoạn và số kWh của mỗi đoạn lấy theo số đo gần ranh giới nhất, nội suy tuyến tính nếu không có số đo đúng mốc
  - Giả sử phiên nằm trọn trong một khung, Khi tính tiền, Thì chỉ có một đoạn và tổng bằng kWh nhân đơn giá
  - Giả sử tổng các đoạn sau làm tròn lệch với tổng tính trên cả phiên, Khi tính tiền, Thì làm tròn ở từng đoạn rồi cộng, và quy tắc đó ghi rõ trên hoá đơn
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** thuật toán chia đoạn là hàm thuần, không đọc cơ sở dữ liệu, để test theo bảng

#### S-31 — Phiên qua nửa đêm tính đúng sang biểu giá ngày hôm sau  *[Story, Sprint 4]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 2 · **Deps:** S-30 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn phiên kéo dài qua 0 giờ áp đúng biểu giá của từng ngày để báo cáo theo ngày không bị lệch
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên từ 23:00 tới 01:00, Khi tính tiền, Thì phần trước 0 giờ tính theo biểu giá ngày hôm trước và phần sau tính theo ngày hôm sau, kể cả khi hai ngày có biểu giá khác nhau
  - Giả sử phiên kéo dài hơn 24 giờ, Khi tính tiền, Thì mỗi ngày là một nhóm đoạn riêng và hoá đơn nhóm theo ngày
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** mọi phép chia theo ngày dùng múi giờ của trạm, không dùng UTC

#### S-32 — Bộ ca kiểm thử tính tiền có đáp án tính tay  *[Story, Sprint 4]*

- **Tier/Priority/Status:** Next / Should / Todo
- **SP:** 2 · **Deps:** S-31 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn xem được bảng ca kiểm thử với đáp án tính tay để tin bộ tính tiền vì nó khớp với số tôi tự tính, không phải vì nó khớp với chính nó
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử bảng ca kiểm thử có ít nhất 12 ca gồm phiên một khung, cắt ranh giới, qua nửa đêm, có phí chiếm trụ, số đo thưa, Khi chạy bộ test, Thì mọi ca khớp đáp án tính tay từng đồng
  - Giả sử một ca sai, Khi test chạy, Thì thông báo nêu rõ ca nào, đoạn nào, chênh bao nhiêu
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** đáp án tính tay lưu trong tệp riêng có tên người tính và ngày, không sinh bằng mã

#### S-33 — Tài xế xem hoá đơn có diễn giải từng đoạn giá  *[Story, Sprint 4]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 3 · **Deps:** S-30, S-22 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn thấy tiền được tính ra sao để tin vào con số thay vì phải chấp nhận một tổng số không giải thích
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên đã kết thúc, Khi mở hoá đơn, Thì thấy từng đoạn kèm khoảng thời gian, số kWh, đơn giá, thành tiền, dòng phí chiếm trụ nếu có, và tổng cộng
  - Giả sử biểu giá đã đổi sau phiên, Khi mở lại hoá đơn, Thì vẫn hiện đúng đơn giá tại thời điểm sạc
  - Giả sử phiên đang ở trạng thái cần xem xét, Khi mở hoá đơn, Thì thấy thông báo đang chờ xử lý thay vì một số tiền tạm
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** hoá đơn lưu thành bản ghi bất biến khi phiên kết thúc, không tính lại mỗi lần mở

#### S-34 — Đổi biểu giá không làm đổi tiền của phiên đã kết thúc  *[Story, Sprint 4]*

- **Tier/Priority/Status:** Next / Should / Todo
- **SP:** 2 · **Deps:** S-33 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn đổi biểu giá từ một ngày trong tương lai để khách đang sạc hôm nay không bị đổi giá giữa chừng
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tôi tạo biểu giá mới có hiệu lực từ ngày mai, Khi lưu, Thì phiên hôm nay vẫn tính theo biểu giá cũ và phiên ngày mai theo biểu giá mới
  - Giả sử tôi cố đặt ngày hiệu lực trong quá khứ, Khi lưu, Thì bị chặn
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** biểu giá cũ không bị xoá, chỉ hết hiệu lực; mọi hoá đơn tham chiếu tới phiên bản biểu giá cụ thể

#### S-65 — Gói thuê bao tháng với biểu giá riêng  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Could / Todo
- **SP:** 3 · **Deps:** S-34, S-37 · **Owner:** chưa phân
- **User story:** Là tài xế đi nhiều tôi muốn mua gói tháng để được đơn giá thấp hơn để tiết kiệm khi sạc thường xuyên
- **Acceptance Criteria (Given/When/Then):**
  - Tài xế có gói còn hạn được áp biểu giá của gói thay vì biểu giá trạm, và hoá đơn ghi rõ đang áp gói nào. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt gói áp cho mọi trạm hay từng chủ trạm, và cách chia doanh thu gói cho đối tác

### E-06 — Ví và thanh toán

**Tier:** Next · **Priority:** Must · **Status:** Todo · **Deps:** E-05 · **Owner:** chưa phân

**Mô tả:** Tài xế nạp tiền vào ví, hệ thống trừ tự động khi phiên kết thúc. Ví không đủ tiền thì không cho bắt đầu phiên mới. Webhook nạp tiền gửi lại nhiều lần chỉ được ghi nhận một. Mọi biến động số dư là một dòng sổ cái chỉ ghi thêm; số dư là tổng của sổ. Chưa có sandbox thanh toán thì đi bằng đường nạp tay (S-36).

**Acceptance (mức epic):** Số dư ví luôn khớp tổng nạp trừ tổng tiêu, không sai một đồng, kể cả khi webhook gửi lại và khi hai phiên kết thúc cùng lúc

**NFR:** không lưu thông tin thẻ; mọi biến động số dư ghi nhật ký không sửa được

#### S-35 — Tài xế nạp tiền vào ví qua cổng thanh toán sandbox  *[Story, Sprint 5]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 5 · **Deps:** S-33 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn nạp tiền vào ví bằng cổng thanh toán để sạc xong là trừ luôn, không phải thao tác thanh toán mỗi lần
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tôi chọn số tiền nạp hợp lệ, Khi bấm nạp, Thì hệ thống tạo giao dịch chờ và chuyển tôi sang trang cổng sandbox
  - Giả sử cổng gửi webhook xác nhận thành công, Khi hệ thống nhận và kiểm chữ ký đúng, Thì số dư tăng đúng số tiền và giao dịch chuyển sang thành công
  - Giả sử tôi quay về ứng dụng trước khi webhook tới, Khi mở ví, Thì thấy giao dịch đang chờ, số dư chưa tăng, và số dư tự cập nhật khi webhook tới
  - Giả sử cổng báo thất bại hoặc tôi huỷ, Khi hệ thống nhận, Thì số dư không đổi và giao dịch ghi lý do
  - Chưa refine đầy đủ — tier Next, SP thô; cổng cụ thể chốt khi có tài khoản sandbox, xem R-02
- **NFR / ràng buộc kỹ thuật:** số dư chỉ tăng khi có webhook đã kiểm chữ ký, không tăng theo trang quay về

#### S-36 — Quản trị viên nạp tay vào ví khi chưa có cổng thanh toán  *[Story, Sprint 5]*

- **Tier/Priority/Status:** Next / Should / Todo
- **SP:** 2 · **Deps:** S-41 · **Owner:** chưa phân
- **User story:** Là quản trị hệ thống tôi muốn cộng tiền vào ví tài xế theo phiếu thu để toàn bộ luồng trừ ví và đối soát vẫn chạy được trong lúc chờ tài khoản sandbox
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tôi nhập số tiền và mã phiếu thu, Khi xác nhận, Thì số dư tăng và sổ cái ghi một dòng có loại nạp tay kèm người thực hiện và mã phiếu
  - Giả sử nhập lại cùng mã phiếu thu, Khi xác nhận, Thì bị chặn vì mã đã dùng
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** chỉ vai trò quản trị có quyền; mọi lần nạp tay hiện trong nhật ký S-56

#### S-37 — Ví bị trừ tự động khi phiên kết thúc, có bản ghi giao dịch  *[Story, Sprint 5]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 3 · **Deps:** S-33, S-41 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn tiền tự trừ khi sạc xong để rút súng là đi được ngay
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử phiên kết thúc và hoá đơn đã lập, Khi hệ thống xử lý, Thì ví bị trừ đúng tổng hoá đơn và sổ cái có một dòng tham chiếu tới phiên
  - Giả sử hai phiên của cùng tài xế kết thúc cùng lúc, Khi hệ thống xử lý, Thì cả hai đều được trừ và số dư cuối bằng số dư đầu trừ tổng hai hoá đơn
  - Giả sử ví không đủ tiền cho phiên vừa xong, Khi hệ thống xử lý, Thì vẫn trừ để số dư âm và tài khoản bị đánh dấu nợ cho tới khi nạp bù
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** trừ ví và lập hoá đơn nằm trong một giao dịch; một phiên không bao giờ bị trừ hai lần

#### S-38 — Ví dưới ngưỡng tối thiểu thì trụ từ chối bắt đầu phiên mới  *[Story, Sprint 5]*

- **Tier/Priority/Status:** Next / Should / Todo
- **SP:** 2 · **Deps:** S-37, S-24 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn chặn phiên mới khi ví khách không đủ tiền để không bị nợ khó đòi
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử số dư dưới ngưỡng tối thiểu cấu hình được, Khi trụ gửi `Authorize` hoặc tài xế bấm bắt đầu trên ứng dụng, Thì trả về `Blocked` và ứng dụng hiện lý do cùng nút nạp tiền
  - Giả sử số dư vừa đủ ngưỡng, Khi bắt đầu phiên, Thì được chấp nhận
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** ngưỡng là tham số cấu hình toàn hệ thống, mặc định bằng tiền của 5 kWh theo giá cao nhất

#### S-39 — Webhook nạp ví gửi lại nhiều lần chỉ ghi nhận một, sai chữ ký bị từ chối  *[Story, Sprint 5]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 3 · **Deps:** S-35 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn một lần nạp chỉ vào ví một lần để sổ sách không sai
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử cổng gửi lại cùng webhook 5 lần, Khi hệ thống nhận, Thì số dư chỉ tăng một lần và năm lần đều trả về thành công cho cổng
  - Giả sử webhook có chữ ký sai hoặc thiếu, Khi hệ thống nhận, Thì trả về 401, không đổi số dư, và ghi nhật ký kèm IP
  - Giả sử webhook tới cho giao dịch không tồn tại, Khi hệ thống nhận, Thì trả về 404 và ghi cảnh báo
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** chống trùng theo mã giao dịch của cổng, lưu ở cơ sở dữ liệu — cùng nguyên tắc với S-14

#### S-40 — Tài xế xem số dư và lịch sử giao dịch ví  *[Story, Sprint 5]*

- **Tier/Priority/Status:** Next / Should / Todo
- **SP:** 2 · **Deps:** S-37 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn xem số dư và từng lần nạp, từng lần trừ để đối chiếu với hoá đơn khi thấy số dư khác mình nghĩ
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tôi mở ví, Khi trang tải, Thì thấy số dư hiện tại và danh sách giao dịch mới nhất trước, mỗi dòng có loại, số tiền, thời điểm và liên kết tới phiên hoặc lần nạp
  - Giả sử tôi gọi API ví bằng mã tài xế khác, Khi máy chủ nhận, Thì trả về 403
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** phân trang 50 dòng

#### S-41 — Số dư ví luôn khớp sổ cái chỉ ghi thêm  *[Story, Sprint 5]*

- **Tier/Priority/Status:** Next / Must / Todo
- **SP:** 3 · **Deps:** S-25 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn mọi biến động số dư là một dòng sổ cái không sửa được và số dư suy ra từ sổ để không bao giờ có con số nào không giải thích được
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử có bất kỳ thao tác nạp hay trừ nào, Khi hệ thống ghi, Thì chỉ chèn một dòng vào bảng sổ cái, không cập nhật tại chỗ
  - Giả sử job kiểm định chạy, Khi so tổng sổ cái với số dư đang hiển thị của từng ví, Thì mọi ví khớp; ví lệch được báo và khoá giao dịch mới cho tới khi người xử lý
  - Giả sử hai giao dịch ghi đồng thời vào cùng ví, Khi cả hai hoàn tất, Thì không dòng nào bị mất
  - Chưa refine đầy đủ — tier Next, SP thô
- **NFR / ràng buộc kỹ thuật:** bảng sổ cái chỉ có quyền chèn và đọc từ ứng dụng, giống `audit_logs` ở T-57

### E-07 — Đặt chỗ trụ sạc

**Tier:** Later · **Priority:** Should · **Status:** Todo · **Deps:** E-06 · **Owner:** chưa phân

**Mô tả:** Tài xế đặt trước một trụ trong khoảng thời gian; hệ thống gửi `ReserveNow` xuống trụ để trụ chỉ nhận đúng thẻ đã đặt. Hai người đặt cùng trụ cùng lúc thì chỉ một người thành công. Giữ chỗ quá giờ không tới thì huỷ và tính phí.

**Acceptance (mức epic):** Bắn nhiều yêu cầu đặt chỗ đồng thời vào cùng một trụ thì đúng một yêu cầu thành công, và trụ ảo từ chối thẻ khác trong lúc đang giữ chỗ

**NFR:** đặt chỗ hết hạn được nhả kể cả khi tiến trình nền vừa khởi động lại

#### S-48 — Tài xế đặt chỗ một trụ trong khoảng thời gian  *[Story, Sprint 7]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 5 · **Deps:** S-47, S-38 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn đặt trước một trụ để đi tới nơi là có chỗ sạc, không phải chờ
- **Acceptance Criteria (Given/When/Then):**
  - Chọn trụ và giờ tới trong vòng 2 giờ tới; hệ thống gửi `ReserveNow` với thẻ của tôi và hạn giữ, trụ trả `Accepted` thì chỗ được giữ và đầu nối hiện `Reserved`; trụ trả `Occupied` hoặc `Rejected` thì báo ngay. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt độ dài giữ chỗ tối đa và có thu phí đặt trước không

#### S-49 — Hai tài xế đặt cùng trụ cùng lúc thì chỉ một người thành công  *[Story, Sprint 7]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-48 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn chắc chắn chỗ mình đặt là của mình để không tới nơi mới biết trụ đã có người
- **Acceptance Criteria (Given/When/Then):**
  - Nhiều yêu cầu đặt chỗ đồng thời vào cùng trụ và cùng khoảng thời gian thì đúng một thành công nhờ ràng buộc ở cơ sở dữ liệu, các yêu cầu còn lại nhận thông báo trụ đã được đặt kèm gợi ý trụ khác. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — bảo đảm chống trùng phải nằm ở tầng cơ sở dữ liệu, cùng nguyên tắc với S-14, không dựa vào khoá trong bộ nhớ

#### S-50 — Giữ chỗ quá giờ không tới thì bị huỷ và tính phí  *[Story, Sprint 7]*

- **Tier/Priority/Status:** Later / Could / Todo
- **SP:** 3 · **Deps:** S-49 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn thu phí khi khách đặt chỗ rồi không tới để trụ không bị giữ vô ích
- **Acceptance Criteria (Given/When/Then):**
  - Quá hạn giữ mà chưa bắt đầu phiên thì đặt chỗ chuyển sang quá hạn, trụ nhận `CancelReservation` và mở lại, ví bị trừ phí không đến theo cấu hình của trạm và có dòng sổ cái. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt mức phí và có miễn phí lần đầu không

#### S-51 — Tài xế huỷ chỗ đã đặt và trụ mở lại cho người khác  *[Story, Sprint 7]*

- **Tier/Priority/Status:** Later / Could / Todo
- **SP:** 3 · **Deps:** S-50 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn huỷ chỗ khi đổi kế hoạch để không bị tính phí không đến
- **Acceptance Criteria (Given/When/Then):**
  - Huỷ trước hạn thì hệ thống gửi `CancelReservation`, đầu nối về `Available`, không tính phí; huỷ sau khi đã quá hạn thì không được vì đã tính phí. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt có cho huỷ miễn phí tới sát giờ không

### E-08 — Phân bổ công suất

**Tier:** Later · **Priority:** Must · **Status:** Todo · **Deps:** E-04 · **Owner:** chưa phân

**Mô tả:** Trạm có tổng công suất giới hạn, nhỏ hơn tổng công suất danh định của các trụ cộng lại. Khi nhiều xe cùng sạc, hệ thống phải chia công suất động và gửi giới hạn xuống từng trụ bằng `SetChargingProfile`. Simulator phải kiểm sớm xem có tôn trọng hồ sơ sạc không, xem R-08.

**Acceptance (mức epic):** Mô phỏng 8 xe vào trạm 100 kW thì tổng công suất cấp không bao giờ vượt 100 kW, và khi một xe rời đi thì xe còn lại được cấp thêm trong vòng 30 giây

**NFR:** chia lại công suất phải xong trong vài giây, không để trụ chờ lâu

#### S-42 — Chủ trạm đặt hạn mức công suất cho trạm  *[Story, Sprint 6]*

- **Tier/Priority/Status:** Later / Must / Todo
- **SP:** 3 · **Deps:** S-05 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn khai báo công suất tối đa của trạm và công suất danh định của từng trụ để hệ thống biết ranh giới cần giữ
- **Acceptance Criteria (Given/When/Then):**
  - Khai được hạn mức trạm tính bằng kW và công suất danh định từng đầu nối; tổng danh định lớn hơn hạn mức được cho phép và hiện cảnh báo trạm đang quá đăng ký. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt đơn vị nhập là kW hay A theo pha

#### S-43 — Tổng công suất cấp cho các trụ đang sạc không vượt hạn mức trạm  *[Story, Sprint 6]*

- **Tier/Priority/Status:** Later / Must / Todo
- **SP:** 5 · **Deps:** S-42, S-17 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn trạm không bao giờ vượt công suất cho phép để không bị nhảy cầu dao và không bị phạt tiền điện công suất
- **Acceptance Criteria (Given/When/Then):**
  - Khi một phiên bắt đầu làm tổng danh định các phiên đang chạy vượt hạn mức, hệ thống gửi `SetChargingProfile` xuống các trụ để tổng giới hạn bằng hoặc dưới hạn mức, chia đều theo số phiên; trụ trả `Rejected` thì phiên đó bị dừng và có cảnh báo. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt cách chia: chia đều, ưu tiên xe sắp đầy, hay ưu tiên theo hạng khách; simulator phải tôn trọng hồ sơ sạc (R-08)

#### S-44 — Công suất được chia lại khi có xe vào hoặc rời trạm  *[Story, Sprint 6]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 5 · **Deps:** S-43 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn được cấp thêm công suất khi xe khác rút ra để sạc nhanh hơn khi trạm vắng
- **Acceptance Criteria (Given/When/Then):**
  - Xe rời trạm hoặc phiên chuyển sang `SuspendedEV` thì trong 30 giây các phiên còn lại nhận hồ sơ sạc mới với giới hạn cao hơn; không gửi hồ sơ mới nếu giới hạn không đổi. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt tần suất chia lại tối thiểu để không gửi lệnh liên tục xuống trụ

#### S-45 — Chủ trạm đặt hạn mức công suất theo khung giờ  *[Story, Sprint 6]*

- **Tier/Priority/Status:** Later / Could / Todo
- **SP:** 3 · **Deps:** S-44, S-29 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn hạ hạn mức công suất vào giờ cao điểm của lưới điện để giảm chi phí tiền điện
- **Acceptance Criteria (Given/When/Then):**
  - Khai được hạn mức khác nhau theo khung giờ; tới ranh giới khung thì các phiên đang chạy nhận hồ sơ sạc mới theo hạn mức mới. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt xử lý khi hạn mức hạ xuống lúc số phiên đang chạy đã vượt

### E-09 — Đối soát và chia doanh thu

**Tier:** Later · **Priority:** Must · **Status:** Todo · **Deps:** E-06 · **Owner:** chưa phân

**Mô tả:** Chủ trạm xem doanh thu và sản lượng kWh; kế toán đối chiếu tổng kWh đã cấp với tổng tiền đã thu, chốt kỳ, và chia doanh thu cho đối tác theo tỉ lệ hợp đồng. Báo cáo đọc từ hoá đơn và sổ cái đã chốt, không tính lại từ số đo thô.

**Acceptance (mức epic):** Tổng kWh nhân đơn giá theo từng đoạn bằng tổng tiền đã thu trong kỳ, chênh lệch bằng 0 hoặc được liệt kê từng phiên có lý do

**NFR:** báo cáo đọc từ dữ liệu đã chốt, không tính lại từ số đo thô mỗi lần mở

#### S-52 — Chủ trạm xem doanh thu và sản lượng kWh theo kỳ, theo từng trụ  *[Story, Sprint 8]*

- **Tier/Priority/Status:** Later / Must / Todo
- **SP:** 3 · **Deps:** S-37 · **Owner:** chưa phân
- **User story:** Là chủ trạm tôi muốn biết trạm của mình bán được bao nhiêu điện và thu bao nhiêu tiền theo ngày, tuần, tháng để quyết định có đầu tư thêm trụ không
- **Acceptance Criteria (Given/When/Then):**
  - Bảng theo kỳ tự chọn có số phiên, tổng kWh, tổng tiền, phí chiếm trụ, chia theo từng trụ; chỉ thấy trạm của mình. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt kỳ mặc định và có cần biểu đồ không

#### S-53 — Kế toán đối soát tổng kWh đã cấp với tổng tiền đã thu  *[Story, Sprint 8]*

- **Tier/Priority/Status:** Later / Must / Todo
- **SP:** 5 · **Deps:** S-52, S-41 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn kiểm tra tiền thu khớp với điện đã bán trong kỳ để phát hiện phiên tính sai hoặc thất thoát
- **Acceptance Criteria (Given/When/Then):**
  - Báo cáo kỳ liệt kê phiên có kWh mà không có hoá đơn, có hoá đơn mà không có dòng sổ cái, hoặc tiền hoá đơn lệch với tính lại từ biểu giá; tổng chênh lệch và danh sách phiên cần xem xét hiện ở đầu báo cáo. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt ngưỡng chênh lệch coi là chấp nhận được do làm tròn

#### S-54 — Chia doanh thu cho đối tác theo tỉ lệ hợp đồng  *[Story, Sprint 8]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-53 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn tính phần doanh thu của từng chủ trạm để chi trả đúng hợp đồng
- **Acceptance Criteria (Given/When/Then):**
  - Mỗi chủ trạm có tỉ lệ chia khai trong hồ sơ đối tác; cuối kỳ hệ thống tính số tiền phải trả cho từng đối tác từ doanh thu đã đối soát và lập bảng kê. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt cách xử lý khi tỉ lệ hợp đồng đổi giữa kỳ và phần phí chiếm trụ có chia không

#### S-55 — Kỳ đối soát được chốt và khoá  *[Story, Sprint 8]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-53 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn chốt kỳ sau khi đối soát xong để không ai sửa được phiên hay hoá đơn của kỳ đã báo cáo
- **Acceptance Criteria (Given/When/Then):**
  - Chốt kỳ làm mọi phiên, hoá đơn và dòng sổ cái trong kỳ trở thành chỉ đọc; phiên bất thường chưa xử lý thì không cho chốt; mở lại kỳ cần vai trò quản trị và được ghi nhật ký. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt kỳ theo tháng dương lịch hay theo hợp đồng

#### S-58 — Xuất báo cáo doanh thu và đối soát ra tệp CSV  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Could / Todo
- **SP:** 2 · **Deps:** S-53 · **Owner:** chưa phân
- **User story:** Là kế toán đối soát tôi muốn tải báo cáo dạng CSV để đưa vào phần mềm kế toán đang dùng
- **Acceptance Criteria (Given/When/Then):**
  - Xuất được báo cáo S-52 và S-53 ra CSV có mã hoá UTF-8 kèm BOM để mở đúng tiếng Việt trong Excel. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt danh sách cột theo phần mềm kế toán đích

### E-10 — Giám sát vận hành và bảo vệ dữ liệu cá nhân

**Tier:** Ready · **Priority:** Must · **Status:** Todo · **Deps:** E-04 · **Owner:** cả team

**Mô tả:** Nhật ký thao tác trên trụ, phiên và ví; cảnh báo trụ hỏng; bảng sức khoẻ hệ thống; và nghĩa vụ xoá dữ liệu cá nhân. Lịch sử sạc cho biết tài xế đã ở đâu vào lúc nào — đây là dữ liệu vị trí, nhạy cảm hơn dữ liệu giao dịch thông thường.

**Acceptance (mức epic):** Truy được ai làm gì trên một phiên sạc hay một giao dịch ví; xoá được dữ liệu cá nhân mà không phá sổ sách kế toán

**NFR:** nhật ký chỉ ghi thêm, không sửa và không xoá được từ giao diện

#### S-27 — Mọi lệnh điều khiển từ xa được ghi nhật ký kèm người thực hiện  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Should / Todo
- **SP:** 1 · **Deps:** S-23 · **Owner:** cả team
- **User story:** Là quản trị hệ thống tôi muốn biết ai đã khởi động lại trụ hay dừng phiên nào lúc nào để trả lời được khi chủ trạm hỏi vì sao khách của họ bị ngắt sạc
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử vận hành viên gửi `Reset` hoặc `RemoteStopTransaction`, Khi lệnh được gửi, Thì có một dòng nhật ký ghi người, lệnh, trụ hoặc phiên, thời điểm, và kết quả trụ trả về
  - Giả sử quản trị viên mở trang nhật ký, Khi lọc theo trụ hoặc theo người trong một khoảng thời gian, Thì thấy đúng các dòng liên quan
  - Giả sử ai đó cố sửa hoặc xoá một dòng nhật ký qua API, Khi máy chủ nhận, Thì trả về 405
- **NFR / ràng buộc kỹ thuật:** bảng nhật ký chỉ có quyền chèn và đọc từ ứng dụng

  **Task kỹ thuật của S-27:**

  - **T-57 — Bảng `audit_logs` chỉ ghi thêm, ghi từ một hàm dùng chung** *(Sprint 3, Todo)*
    - Mô tả: Bảng `audit_logs`: người, hành động, loại đối tượng, mã đối tượng, dữ liệu kèm dạng JSON, thời điểm. Một hàm `ghi_nhat_ky` dùng chung; thay chỗ log tạm ở T-35 và nối vào T-49, T-54. Migration theo mẫu T-36; cấp quyền cơ sở dữ liệu chỉ cho phép chèn và đọc.
    - AC: Gửi `Reset` và dừng phiên thì có đúng hai dòng; câu `UPDATE` hoặc `DELETE` từ tài khoản ứng dụng bị cơ sở dữ liệu từ chối
    - Deps: T-50
    - NFR: không ghi mã thẻ hay dữ liệu định danh vào cột JSON
    - Owner: cả team
  - **T-58 — Màn hình tra nhật ký theo trụ, theo người, theo khoảng thời gian** *(Sprint 3, Todo)*
    - Mô tả: Trang danh sách có ba bộ lọc và phân trang. Bố cục theo T-54. Chỉ vai trò quản trị và vận hành viên vào được.
    - AC: Lọc theo trụ ảo vừa gửi `Reset` thấy đúng dòng đó; phân trang 50 dòng một trang
    - Deps: T-57
    - NFR: truy vấn dùng chỉ mục theo thời điểm
    - Owner: cả team

#### S-46 — Cảnh báo khi trụ ngoại tuyến quá lâu hoặc báo lỗi liên tục  *[Story, Sprint 6]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-12, S-10 · **Owner:** chưa phân
- **User story:** Là vận hành viên tôi muốn được báo khi trụ hỏng để cử người đi sửa trước khi khách phàn nàn
- **Acceptance Criteria (Given/When/Then):**
  - Trụ ngoại tuyến quá ngưỡng hoặc có quá số lần lỗi trong `connector_errors` trong khoảng thời gian cấu hình thì sinh một cảnh báo hiện ở đầu màn hình theo dõi và gửi email; cùng một trụ không tạo cảnh báo mới cho tới khi cảnh báo cũ được đóng. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt ngưỡng và kênh nhận ngoài email

#### S-56 — Nhật ký thao tác trên giao dịch ví truy được ai làm gì  *[Story, Sprint 8]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-27, S-36 · **Owner:** chưa phân
- **User story:** Là quản trị hệ thống tôi muốn truy được ai đã nạp tay, ai đã điều chỉnh ví nào lúc nào để điều tra khi có khiếu nại về số dư
- **Acceptance Criteria (Given/When/Then):**
  - Mọi nạp tay, điều chỉnh, mở khoá ví đều có dòng trong `audit_logs` với người, số tiền, lý do; trang nhật ký S-27 lọc thêm được theo tài xế. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt thời gian lưu nhật ký theo yêu cầu kế toán

#### S-57 — Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển  *[Story, Sprint 8]*

- **Tier/Priority/Status:** Later / Must / Todo
- **SP:** 3 · **Deps:** S-55 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn yêu cầu xoá thông tin cá nhân và lịch sử sạc của mình để thực hiện quyền theo Nghị định 13/2023/NĐ-CP
- **Acceptance Criteria (Given/When/Then):**
  - Sau khi yêu cầu được duyệt, không truy được tài xế đã sạc ở đâu lúc nào — phiên và hoá đơn được ẩn danh hoá thay vì xoá — nhưng số liệu doanh thu tổng hợp và sổ cái vẫn nguyên; ví còn số dư dương thì phải xử lý hoàn tiền trước. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần người có thẩm quyền xác nhận phạm vi dữ liệu phải xoá và dữ liệu phải giữ theo luật kế toán. **Skill không đưa tư vấn pháp lý**

#### S-63 — Bảng sức khoẻ hệ thống: trụ trực tuyến, phiên đang chạy, lỗi gần đây  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Could / Todo
- **SP:** 3 · **Deps:** S-46 · **Owner:** chưa phân
- **User story:** Là quản trị hệ thống tôi muốn một trang tổng quan số trụ trực tuyến, số phiên đang chạy, số tin nhắn lỗi 5 phút qua và độ trễ trả lời trụ để biết hệ thống có ổn trước khi có người gọi báo
- **Acceptance Criteria (Given/When/Then):**
  - Trang tự cập nhật mỗi 30 giây với bốn con số trên và biểu đồ 24 giờ gần nhất. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt có xuất số liệu cho công cụ giám sát ngoài không

### E-11 — Ứng dụng tài xế

**Tier:** Ready · **Priority:** Must · **Status:** Todo · **Deps:** E-04 · **Owner:** cả team

**Mô tả:** Mặt tài xế của hệ thống, chạy trên trình duyệt điện thoại: tìm trạm còn đầu nối rảnh, bắt đầu phiên từ ứng dụng, theo dõi phiên đang sạc, xem lịch sử, nhận thông báo. Không làm app native và không làm định tuyến bản đồ.

**Acceptance (mức epic):** Tài xế đi hết hành trình tìm trạm → bắt đầu sạc → theo dõi → kết thúc → xem hoá đơn trên điện thoại mà không cần ai ở trạm hỗ trợ

**NFR:** mọi màn hình dùng được ở chiều rộng 360px

#### S-22 — Tài xế xem phiên đang sạc của mình cập nhật theo thời gian thực  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Must / Todo
- **SP:** 2 · **Deps:** S-19 · **Owner:** cả team
- **User story:** Là tài xế tôi muốn thấy số điện đã nạp và thời gian đã sạc tăng dần trên điện thoại để đi uống cà phê mà vẫn biết khi nào nên quay lại
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử tôi có một phiên đang sạc, Khi mở ứng dụng, Thì thấy ngay trụ, thời điểm bắt đầu, số kWh mới nhất và thời gian đã sạc
  - Giả sử trụ gửi số đo mới, Khi tôi đang mở màn hình, Thì số kWh đổi trong 2 giây mà không cần tải lại
  - Giả sử tôi không có phiên nào đang sạc, Khi mở ứng dụng, Thì thấy thông báo không có phiên và lối tắt tới tìm trạm
  - Giả sử tôi gọi API phiên bằng mã phiên của tài xế khác, Khi máy chủ nhận, Thì trả về 403
- **NFR / ràng buộc kỹ thuật:** phiên tra theo tài xế đang đăng nhập, không nhận mã phiên từ trình duyệt làm nguồn sự thật

  **Task kỹ thuật của S-22:**

  - **T-47 — API phiên hiện tại của tài xế đang đăng nhập, kèm số kWh mới nhất** *(Sprint 3, Todo)*
    - Mô tả: Endpoint trả về phiên đang sạc của tài xế hiện tại (qua thẻ ở T-32), kèm số đo mới nhất từ T-40. Đi qua middleware T-06 với vai trò tài xế.
    - AC: Tài xế có phiên nhận đúng phiên của mình; không có phiên nhận 204; gọi bằng mã phiên người khác nhận 403
    - Deps: T-42
    - NFR: một truy vấn, không gọi hai lần
    - Owner: cả team
  - **T-48 — Màn hình phiên đang sạc, số kWh tăng dần không cần tải lại** *(Sprint 3, Todo)*
    - Mô tả: Màn hình điện thoại hiện trụ, thời gian, số kWh; nhận cập nhật qua kênh đẩy đã dựng ở T-25, lọc theo phiên của tài xế. Đây là màn hình đầu tiên phía tài xế — bố cục di động của nó là mẫu cho T-52 và các màn hình E-11 sau.
    - AC: Trụ ảo gửi số đo thì màn hình đổi trong 2 giây; xoay ngang màn hình vẫn đọc được
    - Deps: T-47
    - NFR: dùng được ở chiều rộng 360px
    - Owner: cả team

#### S-24 — Tài xế bắt đầu phiên từ ứng dụng bằng `RemoteStartTransaction`  *[Story, Sprint 3]*

- **Tier/Priority/Status:** Ready / Should / Todo
- **SP:** 2 · **Deps:** S-17, S-16 · **Owner:** cả team
- **User story:** Là tài xế tôi muốn bấm bắt đầu sạc trên điện thoại sau khi cắm súng để không cần mang thẻ
- **Acceptance Criteria (Given/When/Then):**
  - Giả sử đầu nối đang rảnh và tôi đã cắm súng, Khi bấm bắt đầu sạc, Thì hệ thống gửi `RemoteStartTransaction` với thẻ ảo của tôi, trụ trả `Accepted`, và phiên xuất hiện khi trụ gửi `StartTransaction`
  - Giả sử trụ trả `Rejected`, Khi hệ thống nhận, Thì tôi thấy thông báo trụ từ chối và gợi ý kiểm tra súng đã cắm chưa
  - Giả sử đầu nối đang bận hoặc đang được đặt chỗ bởi người khác, Khi bấm bắt đầu, Thì bị chặn ngay ở máy chủ, không gửi lệnh xuống trụ
  - Giả sử trụ trả `Accepted` nhưng không gửi `StartTransaction` trong 60 giây, Khi hết thời gian, Thì tôi thấy thông báo chưa bắt đầu được và có thể thử lại
- **NFR / ràng buộc kỹ thuật:** mỗi tài xế có một thẻ ảo trong `id_tags` để đi chung đường xác thực với thẻ vật lý

  **Task kỹ thuật của S-24:**

  - **T-51 — API bắt đầu phiên kiểm đầu nối rảnh rồi gửi `RemoteStartTransaction`** *(Sprint 3, Todo)*
    - Mô tả: Endpoint nhận mã đầu nối, kiểm trạng thái rảnh từ `connectors`, kiểm trạm đang hoạt động, gửi lệnh qua T-34 với thẻ ảo của tài xế. Lưu một bản ghi "đang chờ bắt đầu" có hạn 60 giây để T-52 hỏi trạng thái.
    - AC: Đầu nối rảnh thì trụ ảo bắt đầu phiên; đầu nối bận thì API trả 409 và không có lệnh nào đi xuống trụ
    - Deps: T-37, T-34
    - NFR: thẻ ảo được tạo cùng lúc tạo tài khoản tài xế
    - Owner: cả team
  - **T-52 — Nút bắt đầu sạc trên màn hình trụ, xử lý trụ từ chối hoặc không trả lời** *(Sprint 3, Todo)*
    - Mô tả: Màn hình chi tiết trụ với danh sách đầu nối và nút bắt đầu; trạng thái chờ tối đa 60 giây; ba thông báo cho từ chối, bận, hết thời gian. Bố cục theo T-48.
    - AC: Bốn ca của S-24 đều đúng trên trụ ảo; thành công thì tự chuyển sang màn hình phiên T-48
    - Deps: T-51, T-48
    - NFR: nút bị vô hiệu trong lúc chờ để không gửi hai lệnh
    - Owner: cả team

#### S-47 — Tài xế tìm trạm gần và thấy đầu nối nào đang rảnh  *[Story, Sprint 7]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 5 · **Deps:** S-22, S-29 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn tìm trạm gần vị trí của mình và biết trạm nào còn đầu nối rảnh để không lái tới một trạm đang kín chỗ
- **Acceptance Criteria (Given/When/Then):**
  - Danh sách trạm đang hoạt động sắp theo khoảng cách từ vị trí trình duyệt cung cấp, mỗi trạm hiện số đầu nối rảnh trên tổng số, loại đầu nối, và đơn giá hiện tại; không có vị trí thì cho tìm theo tên hoặc địa chỉ. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — không làm định tuyến bản đồ; cần chốt có nhúng bản đồ tĩnh không

#### S-59 — Tài xế nhận thông báo khi phiên kết thúc hoặc bị dừng  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-37 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn được báo khi sạc xong hoặc bị vận hành viên dừng để quay lại lấy xe trước khi bị tính phí chiếm trụ
- **Acceptance Criteria (Given/When/Then):**
  - Phiên kết thúc, bị dừng từ xa, hoặc bắt đầu tính phí chiếm trụ thì tài xế nhận thông báo trong ứng dụng và email kèm số kWh và tiền tạm tính. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt có làm thông báo đẩy trình duyệt không

#### S-64 — Tài xế xem lịch sử phiên sạc của mình  *[Story, Chưa xếp]*

- **Tier/Priority/Status:** Later / Should / Todo
- **SP:** 3 · **Deps:** S-33 · **Owner:** chưa phân
- **User story:** Là tài xế tôi muốn xem lại các phiên đã sạc kèm hoá đơn để đối chiếu chi tiêu theo tháng
- **Acceptance Criteria (Given/When/Then):**
  - Danh sách phiên đã kết thúc mới nhất trước, mỗi dòng có trạm, thời gian, kWh, tiền, và mở được hoá đơn S-33; lọc theo tháng. Chưa refine — tier Later
- **NFR / ràng buộc kỹ thuật:** chưa refine — cần chốt có cho tải hoá đơn PDF không

## 6. Rủi ro

| ID | Rủi ro | Ảnh hưởng | Khả năng | Giảm thiểu | Chủ |
| --- | --- | --- | --- | --- | --- |
| R-01 | Đặc tả OCPP dài và lạ, team đọc cả tuần vẫn chưa viết được dòng nào | Cao | Cao | K-01 là spike timebox 2 ngày có người hướng dẫn, đầu ra cụ thể là bản ghi chuỗi tin nhắn thật. Chỉ đọc phần đặc tả của 8 tin nhắn liệt kê trong K-01, bỏ phần còn lại | cả team |
| R-02 | **Chưa có tài khoản sandbox thanh toán**, S-35 ở Sprint 5 tắc | Cao | Cao | Nộp hồ sơ ngay ngày đầu Sprint 1. S-36 nạp tay là đường dự phòng đã nằm sẵn trong Sprint 5 để luồng trừ ví và đối soát vẫn chạy | người phụ trách dự án |
| R-03 | Team chống trùng tin nhắn và chống trùng đặt chỗ bằng biến trong bộ nhớ, khởi động lại là mất sạch | Cao | Trung bình | NFR của S-14, S-39, S-49 ghi rõ phải lưu ở cơ sở dữ liệu; T-31 có ca khởi động lại tiến trình giữa hai lần gửi để lộ lỗi này | cả team |
| R-04 | Bộ tính tiền sai ở ca biên (qua nửa đêm, đúng ranh giới khung, số đo thưa) mà không ai phát hiện vì test viết theo chính mã | Cao | Cao | S-32 là story riêng: bộ ca kiểm thử với **đáp án tính tay** lưu trong tệp có tên người tính; thuật toán chia đoạn là hàm thuần (S-30) | cả team |
| R-05 | Sprint 4–8 mới có SP thô; velocity thực sau Sprint 3 có thể khác xa 20 SP/sprint | Trung bình | Cao | Đo velocity 3 sprint đầu rồi tính lại toàn bộ kế hoạch; 25 SP đệm là chỗ cắt trước; story 5 SP tách nhỏ ở Refinement trước khi kéo vào | Scrum Master |
| R-06 | Không có DevOps nên staging hỏng giữa sprint không ai sửa nhanh, và 20 trụ ảo làm máy chủ quá tải | Trung bình | Trung bình | E-01 xong ngay Sprint 1; triển khai thất bại thì giữ bản cũ (T-03); số trụ ảo là tham số, CI chạy ít trụ hơn staging (T-55) | cả team |
| R-07 | Lịch sử sạc là dữ liệu vị trí, xử lý sai thành rủi ro pháp lý | Trung bình | Thấp | S-57 ghi rõ cần người có thẩm quyền xác nhận phạm vi; log không ghi mã thẻ (S-15); **skill không đưa tư vấn pháp lý** | người quyết sản phẩm |
| R-08 | Simulator mã nguồn mở không tôn trọng `SetChargingProfile`, E-08 không kiểm chứng được bằng trụ ảo | Cao | Trung bình | Kiểm ngay trong K-01 xem simulator đã chọn có xử lý hồ sơ sạc không; nếu không thì chọn simulator khác trước Sprint 6 hoặc chấp nhận kiểm E-08 bằng log lệnh đã gửi thay vì công suất thật | cả team |
| R-09 | 5 người mới cùng sửa module xử lý tin nhắn OCPP, xung đột merge và chờ review nuốt capacity | Trung bình | Cao | Mỗi handler một file theo mẫu T-16; chia story theo handler để hai người không cùng đụng một file; Daily Scrum nêu rõ ai chờ review của ai | Scrum Master |

## 7. Definition of Done / Definition of Ready

### Definition of Done (DoD)
- Code review đã duyệt bởi ít nhất một thành viên khác
- Unit test cho nhánh logic mới; độ phủ trên phần thay đổi không giảm
- CI xanh: build, lint, typecheck, test, và kịch bản trụ ảo (từ Sprint 3)
- Không có secret trong mã nguồn; quét phụ thuộc sạch
- AC pass trên staging với **trụ ảo chạy thật**, không chỉ bằng test đơn vị
- Story chạm tiền: có bộ ca kiểm thử với đáp án tính tay
- Story chạm tin nhắn OCPP: xử lý hai lần cho kết quả giống xử lý một lần
- Story có job nền: chạy job hai lần liên tiếp không gây tác dụng phụ
- Không log dữ liệu định danh cá nhân, mã thẻ, và không log thông tin thanh toán
- README cập nhật nếu đổi hành vi công khai hoặc thêm biến môi trường

### Definition of Ready (DoR)
- **[Bắt buộc]** Đủ nhỏ để Done trong 1 sprint
- **[Bắt buộc]** Dependency ngoài đã có cam kết (tài khoản sandbox thanh toán, xem R-02)
- [Khuyến nghị] Có AC viết dạng Giả sử / Khi / Thì (hướng dẫn)
- [Khuyến nghị] Đã ước lượng story point và thay SP thô bằng SP đã cân nhắc (hướng dẫn)
- [Khuyến nghị] Story `Ready` đã có task con ≤ nửa ngày (hướng dẫn, theo profile thực tập)
- [Khuyến nghị] Team hiểu story nói gì mà không cần hỏi lại người viết (hướng dẫn)
