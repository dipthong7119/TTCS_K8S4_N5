# Bao cao ket qua Backend QA Sprint 1

**Nguoi thuc hien**: Ta Nhu Vinh
**Branch**: TA-VINH
**Source kiem thu**: `main@c1084f8799d5612a8b486d95a5afae5becb26d57`
**Ngay kiem thu**: 2026-09-25
**Moi truong**: Windows, Python 3.11.2, SQLite

## Lenh thuc thi

```powershell
python -m venv <test-venv>
<test-venv>\Scripts\python.exe -m pip install -r backend\requirements.txt
<test-venv>\Scripts\python.exe -m pytest tests
<test-venv>\Scripts\python.exe -m ruff check tests
```

## Lan chay tren moi truong sach

Pytest dung ngay khi load `tests/conftest.py`:

```text
ImportError: email-validator is not installed, run `pip install 'pydantic[email]'`
```

Nguyen nhan: `backend/app/schemas/user.py` dung `EmailStr`, nhung
`backend/requirements.txt` khong khai bao `email-validator`. Day la blocker cua
source, khong phai dependency cua test. Da ghi nhan tai GitHub Issue #9.

De tiep tuc danh gia chuc nang, QA cai tam `email-validator` trong virtual
environment, khong sua source Backend.

## Ket qua pytest sau khi go blocker dependency

```text
collected 12 items
7 passed
5 failed
6 warnings
```

| Test case | Ket qua |
| --- | --- |
| Sai email va sai mat khau tra cung loi chung | PASS |
| Thong bao sai thong tin khop SSD-1 | FAIL |
| Lan thu 6 bi khoa trong 15 phut | PASS |
| Thong bao khoa khop SSD-1 | FAIL |
| Trang thai khoa con sau khi tao lai TestClient | PASS |
| Gioi han dang nhap sai theo IP | FAIL |
| Dang nhap thanh cong tao HttpOnly cookie va reset bo dem | PASS |
| Health response khop test contract | FAIL |
| Migration upgrade va downgrade | PASS |
| Seed dung 5 role | PASS |
| `users.email` unique | PASS |
| Mat khau tai khoan demo hoat dong | FAIL |

## Chi tiet loi

### 1. Thong bao sai thong tin khong khop SSD-1

- Mong doi: `email hoặc mật khẩu không đúng` theo SSD-1.
- Thuc te: Backend tra chuoi khong dau `email hoac mat khau khong dung`.
- Test: `test_wrong_credentials_message_matches_specification`.
- Issue: #6.

### 2. Thong bao khoa khong khop SSD-1

- Mong doi: `tài khoản tạm khoá 15 phút` theo SSD-1.
- Thuc te: `tai khoan tam khoa, vui long thu lai sau` khong neu 15 phut.
- Test: `test_locked_message_matches_specification`.
- Issue: #6.

### 3. Chua gioi han dang nhap sai theo IP

- Mong doi: Sau 5 lan sai tu cung IP, request tiep theo bi gioi han.
- Thuc te: Doi email moi cho moi request van tiep tuc thu dang nhap.
- Test: `test_repeated_failures_from_same_ip_are_rate_limited`.
- Issue: #8.

### 4. Health response khong khop contract test hien co

- Mong doi: `Hệ thống đang hoạt động ổn định` theo test contract hien co.
- Thuc te: Backend tra chuoi khong dau.
- Test: `test_health_check_matches_contract`.
- Issue: #5.

### 5. Tai khoan demo khong xac thuc duoc

- Mong doi: 5 tai khoan demo dang nhap duoc bang mat khau trong README.
- Thuc te: Hash seed co dang `=19=...`, khong phai Argon2id hop le.
- Test: `test_seeded_demo_users_have_working_documented_passwords`.
- Issue: #4.

## Ket qua lint test

```text
ruff check tests
All checks passed!
```

## Pham vi bi chan

| Hang muc | Ly do |
| --- | --- |
| SCRUM-102 / T-06 | Chua co `backend/app/core/deps.py` tren main |
| SCRUM-103 / T-07 | Chua co ownership service va station API tren main |
| K-01 | Chua co OCPP simulator va WebSocket gateway tren main |

## Ket luan

Backend chua dat Definition of Done. Bo test da chay duoc sau khi cai tam
dependency bi thieu, nhung con 5 test fail do source va 3 hang muc chua co code
de kiem thu. Khong sua code developer de lam test pass.
