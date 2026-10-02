# Báo cáo kết quả Backend QA Sprint 1

**Người thực hiện**: Tạ Như Vinh
**Branch**: TA-VINH
**Source kiểm thử**: `main@c1084f8799d5612a8b486d95a5afae5becb26d57`
**Ngày kiểm thử**: 2026-09-25
**Môi trường**: Windows, Python 3.11.2, SQLite

## Lệnh thực thi

```powershell
python -m venv <test-venv>
<test-venv>\Scripts\python.exe -m pip install -r backend\requirements.txt
<test-venv>\Scripts\python.exe -m pytest tests
<test-venv>\Scripts\python.exe -m ruff check tests
```

## Lần chạy trên môi trường sạch

Pytest dừng ngay khi load `tests/conftest.py`:

```text
ImportError: email-validator is not installed, run `pip install 'pydantic[email]'`
```

Nguyên nhân: `backend/app/schemas/user.py` dùng `EmailStr`, nhưng
`backend/requirements.txt` không khai báo `email-validator`. Đây là blocker của
source, không phải dependency của test. Đã ghi nhận tại GitHub Issue #9.

Để tiếp tục đánh giá chức năng, QA cài tạm `email-validator` trong virtual
environment, không sửa source Backend.

## Kết quả pytest sau khi gỡ blocker dependency

```text
collected 12 items
7 passed
5 failed
6 warnings
```

| Test case | Kết quả |
| --- | --- |
| Sai email và sai mật khẩu trả cùng lỗi chung | PASS |
| Thông báo sai thông tin khớp SSD-1 | FAIL |
| Lần thứ 6 bị khóa trong 15 phút | PASS |
| Thông báo khóa khớp SSD-1 | FAIL |
| Trạng thái khóa còn sau khi tạo lại TestClient | PASS |
| Giới hạn đăng nhập sai theo IP | FAIL |
| Đăng nhập thành công tạo HttpOnly cookie và reset bộ đếm | PASS |
| Health response khớp test contract | FAIL |
| Migration upgrade và downgrade | PASS |
| Seed đúng 5 role | PASS |
| `users.email` unique | PASS |
| Mật khẩu tài khoản demo hoạt động | FAIL |

## Chi tiết lỗi

### 1. Thông báo sai thông tin không khớp SSD-1

- Mong đợi: `email hoặc mật khẩu không đúng` theo SSD-1.
- Thực tế: Backend trả chuỗi không dấu `email hoac mat khau khong dung`.
- Test: `test_wrong_credentials_message_matches_specification`.
- Issue: #6.

### 2. Thông báo khóa không khớp SSD-1

- Mong đợi: `tài khoản tạm khoá 15 phút` theo SSD-1.
- Thực tế: `tai khoan tam khoa, vui long thu lai sau` không nêu 15 phút.
- Test: `test_locked_message_matches_specification`.
- Issue: #6.

### 3. Chưa giới hạn đăng nhập sai theo IP

- Mong đợi: Sau 5 lần sai từ cùng IP, request tiếp theo bị giới hạn.
- Thực tế: Đổi email mới cho mỗi request vẫn tiếp tục thử đăng nhập.
- Test: `test_repeated_failures_from_same_ip_are_rate_limited`.
- Issue: #8.

### 4. Health response không khớp contract test hiện có

- Mong đợi: `Hệ thống đang hoạt động ổn định` theo test contract hiện có.
- Thực tế: Backend trả chuỗi không dấu.
- Test: `test_health_check_matches_contract`.
- Issue: #5.

### 5. Tài khoản demo không xác thực được

- Mong đợi: 5 tài khoản demo đăng nhập được bằng mật khẩu trong README.
- Thực tế: Hash seed có dạng `=19=...`, không phải Argon2id hợp lệ.
- Test: `test_seeded_demo_users_have_working_documented_passwords`.
- Issue: #4.

## Kết quả lint test

```text
ruff check tests
All checks passed!
```

## Phạm vi bị chặn

| Hạng mục | Lý do |
| --- | --- |
| SCRUM-102 / T-06 | Chưa có `backend/app/core/deps.py` trên main |
| SCRUM-103 / T-07 | Chưa có ownership service và station API trên main |
| K-01 | Chưa có OCPP simulator và WebSocket gateway trên main |

## Kết luận

Backend chưa đạt Definition of Done. Bộ test đã chạy được sau khi cài tạm
dependency bị thiếu, nhưng còn 5 test fail do source và 3 hạng mục chưa có code
để kiểm thử. Không sửa code developer để làm test pass.
