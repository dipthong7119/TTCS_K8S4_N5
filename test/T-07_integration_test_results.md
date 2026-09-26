# Kết quả Integration Test T-07 — Lọc sở hữu trạm (403 + log)

**Người thực hiện**: Hoàng Minh Đức
**Task**: T-07 / SPRINT_1.md — Lọc theo quyền sở hữu ở tầng truy vấn
**Branch**: main
**Ngày thực thi**: 2026-09-26
**Môi trường**: Windows, Python 3.14.7, SQLite in-memory (StaticPool)

---

## Lệnh thực thi

```powershell
cd backend
uv venv .venv
uv pip install -r requirements.txt passlib bcrypt --python .venv\Scripts\python.exe
& ".venv\Scripts\python.exe" -m pytest app/tests/ -v
```

---

## Kết quả pytest — 8/8 PASSED ✅

```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\TTCS_K8S4_N5\backend
configfile: pytest.ini
plugins: anyio-4.15.1, asyncio-1.4.0
collected 8 items

app/tests/integration/test_ownership_access.py::TestCrossOwnerAccess::test_get_other_owner_station_returns_403    PASSED
app/tests/integration/test_ownership_access.py::TestCrossOwnerAccess::test_put_other_owner_station_returns_403    PASSED
app/tests/integration/test_ownership_access.py::TestCrossOwnerAccess::test_delete_other_owner_station_returns_403 PASSED
app/tests/integration/test_ownership_access.py::TestSameOwnerAccess::test_get_own_station_returns_200             PASSED
app/tests/unit/test_ownership.py::test_filter_by_owner_admin_sees_all                                             PASSED
app/tests/unit/test_ownership.py::test_filter_by_owner_station_owner_sees_only_their_stations                     PASSED
app/tests/unit/test_ownership.py::test_filter_by_owner_driver_sees_nothing                                        PASSED
app/tests/unit/test_placeholder.py::test_health_check                                                             PASSED

======================= 8 passed, 19 warnings in 4.86s ========================
```

---

## Chi tiết test case

### Integration — `tests/integration/test_ownership_access.py` (MỚI T-07)

| Test case | Route | Kết quả |
|-----------|-------|---------|
| Owner A gọi GET trạm của B → 403 + 1 dòng log WARNING | `GET /api/stations/{id}` | ✅ PASS |
| Owner A gọi PUT trạm của B → 403 + 1 dòng log WARNING | `PUT /api/stations/{id}` | ✅ PASS |
| Owner A gọi DELETE trạm của B → 403 + 1 dòng log WARNING | `DELETE /api/stations/{id}` | ✅ PASS |
| Owner A gọi GET trạm của chính mình → 200 | `GET /api/stations/{id}` | ✅ PASS |

Mỗi test âm (403) assert thêm:
- Có đúng **1 dòng** log mức `WARNING` với logger `csms.ownership`.
- Nội dung log chứa `ACCESS_DENIED`, `user_id=<owner_a.id>`, `station_id=<station_b.id>`.

### Unit — `tests/unit/test_ownership.py` (không thay đổi)

| Test case | Kết quả |
|-----------|---------|
| Admin thấy tất cả trạm (`filter_by_owner` bỏ qua lọc) | ✅ PASS |
| Chủ trạm chỉ thấy trạm của mình | ✅ PASS |
| Tài xế không thấy trạm nào | ✅ PASS |

---

## Blocker đã giải quyết trong T-07

| Blocker (báo cáo QA cũ) | Trạng thái sau T-07 |
|--------------------------|---------------------|
| SCRUM-103 / T-07: `ownership.py` và API station chưa có | ✅ Đã hoàn thành — `ownership.py` + `stations.py` đầy đủ 4 route |
| SCRUM-102 / T-06: `deps.py` chưa có | ✅ Đã hoàn thành ở T-06 trước đó |

> K-01 (OCPP simulator) và WebSocket gateway vẫn nằm ngoài phạm vi Sprint 1 backend hiện tại.

---

## Fix kỹ thuật trong `conftest.py`

Trong quá trình chạy test, phát hiện 2 vấn đề ở `backend/app/tests/conftest.py` và đã sửa:

### 1. `StaticPool` cho SQLite `:memory:`

**Vấn đề**: Thiếu `StaticPool` khiến SQLite in-memory tạo connection mới cho mỗi request qua `TestClient`, dẫn đến `OperationalError: no such table: users`.

**Fix**:
```python
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # đảm bảo 1 connection duy nhất
)
```

### 2. Thay `passlib/bcrypt` → `argon2-cffi`

**Vấn đề**: `passlib 1.7.4` không tương thích với `bcrypt 5.x`, gây `ValueError: password cannot be longer than 72 bytes`.

**Fix**: Dùng `hash_password` từ `app.core.security` (argon2id) — nhất quán với production code.

```python
# Trước
from passlib.context import CryptContext
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd_ctx.hash("TestPass123!")

# Sau
from app.core.security import hash_password
hashed = hash_password("TestPass123!")
```

---

## Kết luận

T-07 đạt Definition of Done:
- ✅ 8/8 tests xanh (4 integration + 3 unit ownership + 1 health check)
- ✅ Điều kiện sở hữu nằm đúng 1 nơi (`services/ownership.py`)
- ✅ Không có `owner_id == current_user.id` bị chép tay trong router
- ✅ Log WARNING đúng format, không chứa PII
- ✅ Hướng dẫn curl tái hiện thủ công có trong `README.md` và docstring test
