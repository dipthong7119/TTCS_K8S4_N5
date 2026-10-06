# Sắp xếp thư mục dự án

Ngày thực hiện: **06/10/2026**. Đây là thay đổi vị trí file theo yêu cầu người
dùng, không triển khai thêm task Sprint 3 sau T-55.

## Các thay đổi thực tế

| Vị trí trước | Vị trí hiện tại | Mục đích |
| --- | --- | --- |
| `backend/app/tests/` | `backend/tests/` | Tách 21 file unit test/fixture khỏi package ứng dụng. |
| `tests/backend_qa_prompt.md` | `prompts/backend_qa_prompt.md` | Gom prompt về thư mục dành cho agent. |
| `tests/backend_test_results.md` | `ketqua/backend_test_results.md` | Gom báo cáo QA, giữ kết quả lịch sử. |
| `tests/backend_qa_prompt_ket_qua.md` | `ketqua/backend_qa_prompt_ket_qua.md` | Gom báo cáo thực thi prompt. |
| `tests/test_cases_duc_sprint2.md` | `huongdan/test_cases_duc_sprint2.md` | Kịch bản kiểm thử thủ công nằm cùng tài liệu hướng dẫn. |
| `Phan_cong_Sprint3.md` ở gốc | `huongdan/Phan_cong_Sprint3.md` | Phân công nằm cùng kế hoạch. |
| Workbook `.xlsx` ở gốc | Cùng tên trong `huongdan/` | Gom backlog/tasks; không đổi tên hay nội dung workbook. |
| `huongdan/HD.txt` và `hướng dẫn clone push.txt` | `huongdan/git_clone_push.md` | Gom hướng dẫn Git trùng nhau, sửa URL clone và câu lệnh remote không hợp lệ. |
| `huongdan/HDprompt.txt` | Đã loại khỏi repo; bản sao tạm đưa vào Thùng rác | Chỉ chứa dòng thử `hello`/`sv net`, không có prompt nghiệp vụ. |
| 21 thư mục cache | Đã dọn khỏi workspace; bản lưu tạm đưa vào Thùng rác | Dọn `__pycache__`, pytest, Ruff, Mypy khỏi workspace. |

Thư mục gốc giữ README, script khởi chạy, Compose và cấu hình Git/môi trường.
Các nhóm chính là `backend`, `frontend`, `tests`, `prompts`, `huongdan`, `ketqua`.
`.github` chứa workflow; `.venv` và database được giữ để tiếp tục chạy local.
Theo yêu cầu tiếp theo của người dùng, thư mục `backups/` đã được bỏ khỏi dự án;
Compose lưu dump PostgreSQL trong volume `postgres_backups` để không tạo lại thư mục.

## Đường dẫn đã cập nhật

- `backend/pytest.ini`: mặc định thu thập `tests/` trong backend.
- CI/CD: từ `backend`, pytest chạy `tests ../tests`; Ruff kiểm thêm `tests`
  trong backend để các unit test được lint như trước.
- `backend/pyproject.toml`: sửa đường dẫn exclude test và bỏ omit coverage
  của thư mục cũ đã không còn trong package ứng dụng.
- `.dockerignore`: bỏ `backend/tests` khỏi build context; image runtime không
  chứa `app/tests` hoặc `tests`.
- Ba file unit test dùng đường dẫn tương đối tới migration được cập nhật
  chỉ số `Path.parents`; giữ nguyên assertion và nội dung kiểm thử.
- README, ba prompt nền tảng, prompt QA và báo cáo liên quan dùng đường dẫn mới.
  Báo cáo lịch sử được chú thích, các kết quả cũ giữ nguyên.

## Kiểm chứng sau di chuyển

| Kiểm tra | Kết quả |
| --- | --- |
| Pytest đầy đủ trên Windows/Python 3.14.2 | **321 passed**, 59,74s |
| Thu thập mặc định từ backend | **245 unit tests**, dùng đúng `backend/tests` |
| Hành vi JavaScript | **25 passed** |
| Ruff | Đạt với `app tests alembic ../tests` |
| Mypy | Đạt, 41 file ứng dụng |
| Coverage | Giữ 63% |
| Docker build | Image `csms-app:reorg-check` build thành công |
| Docker runtime | Không có thư mục test trong image |
| Linux/Python 3.11.16 | Thu thập toàn bộ test theo đường dẫn CI không lỗi; 3 test truy cập migration được chạy và đạt |
| Bảo toàn test | Đủ 21 file; 18 file khớp byte/hash bản sao, 3 file chỉ sửa đường dẫn tài nguyên |
| Workbook Excel | SHA256 trước/sau giống nhau |
| Git diff | Không có lỗi whitespace |

SHA256 workbook:
`C106E9B5E8458F2F02EF00604BDDED75882E9CFAF4D60C32EECCF2837471BA30`.

## Cache và bản sao tạm

Trước khi di chuyển đã lưu bản sao tạm và kiểm hash của các file liên quan.
Theo yêu cầu người dùng ngày 06/10/2026, thư mục
`E:\TTCS_K8S4_N5_reorg_backup_20261006_122149` đã được chuyển vào Thùng rác Windows,
bao gồm bản sao file, manifest và 21 thư mục cache (21,23 MB). Thư mục backup
tạm không còn ở vị trí cũ. Lệnh xoá vĩnh viễn bị kiểm duyệt tự động chặn nên
dùng thao tác chuyển vào Thùng rác. Cache có thể được công cụ tạo lại khi chạy.

File `.env`, database và migration không bị di chuyển/xoá. Thư mục `backups/`
trong dự án trống lúc kiểm tra, đã được dọn; nơi lưu dump chuyển sang volume Docker.
Các thay đổi T-55 và các file người dùng đã xoá trước lượt này được giữ nguyên.
Chưa commit/push hoặc chạy workflow trên GitHub; các lệnh CI đã được cập nhật và
kiểm tra local theo cấu trúc mới.

## Bỏ thư mục `backups/` ở gốc

- `docker-compose.yml` dùng volume Docker `postgres_backups` tại `/backups`
  trong container, thay cho bind mount `./backups`.
- Chuẩn hoá `backend/scripts/backup_postgres.sh` về LF đúng với `.gitattributes`;
  bản working copy CRLF trước đó làm Alpine shell báo `illegal option`.
- Chạy thử với PostgreSQL 15 riêng, có bảng và dữ liệu mẫu: tạo dump thành công,
  `pg_restore --list` xác nhận hợp lệ, container mới đọc được dump trong volume.
- Sau chạy thử, thư mục `backups/` không xuất hiện lại. Container, network và
  volume của phép thử đã được dọn; dữ liệu PostgreSQL của dự án được giữ nguyên.
- Kiểm thử workflow triển khai: **6 passed**. README và codebase map đã cập nhật
  nơi lưu dump; giữ chức năng sao lưu PostgreSQL của Sprint 1.
