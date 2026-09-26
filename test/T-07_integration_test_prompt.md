# Prompt Backend QA — Task T-07: Integration Test Lọc sở hữu trạm

**Người thực hiện**: Tạ Như Vinh
**Vai trò**: Backend QA / Integration Tester
**Branch**: TA-VINH
**Ngày**: 2026-09-26

---

## Ngữ cảnh (Context)

Dự án CSMS (Nền tảng vận hành trạm sạc xe điện). Tài liệu tham chiếu:
- `prompts/01_CODEBASE_MAP.md` — quy tắc vị trí file (unit test = hàm thuần, integration test = qua DB thật/TestClient)
- `prompts/02_CODING_STANDARDS.md` — quy chuẩn code, log không PII
- `prompts/SPRINT_1.md` — T-07 AC/NFR

Sau khi T-07 hoàn thành, `backend/app/services/ownership.py` và `backend/app/routers/stations.py` đã có đầy đủ. Các blocker trong báo cáo QA cũ (`tests/backend_qa_prompt_ket_qua.md`) đã được giải quyết:
- ✅ T-06: `backend/app/core/deps.py` đã có
- ✅ T-07: `backend/app/services/ownership.py` và API station đã có

---

## Nhiệm vụ (Tasks)

Viết và chạy bộ integration test HTTP-level cho T-07. Dùng `TestClient` FastAPI + SQLite in-memory (không cần server thật).

### 1. File test chính — `backend/app/tests/integration/test_ownership_access.py`

Tạo thư mục `backend/app/tests/integration/` (chưa có) và file test gồm:

**Test case âm — 403 khi truy cập chéo:**

Fixture cần dùng: `two_owners_with_stations` (đã có trong `conftest.py`) trả về `(owner_a, station_a, owner_b, station_b)`.

Với mỗi route sau, đăng nhập bằng `owner_a`, gọi vào `station_b` (thuộc `owner_b`), assert:
- HTTP status = `403`
- `caplog` bắt đúng **1 dòng** WARNING từ logger `csms.ownership`, nội dung chứa `ACCESS_DENIED`, `user_id` của A, `station_id` của B

| Route | Method |
|-------|--------|
| `/api/stations/{station_b.id}` | GET |
| `/api/stations/{station_b.id}` | PUT |
| `/api/stations/{station_b.id}` | DELETE |

**Test case dương — 200 khi truy cập trạm của chính mình:**

Đăng nhập bằng `owner_a`, gọi `GET /api/stations/{station_a.id}`, assert:
- HTTP status = `200`
- `data["id"] == station_a.id` và `data["owner_id"] == owner_a.id`

### 2. Fix `conftest.py` nếu cần

Khi chạy integration test, nếu gặp lỗi `OperationalError: no such table` → thêm `StaticPool` vào `test_engine`:

```python
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
```

Nếu gặp lỗi bcrypt/passlib → thay bằng `hash_password` từ `app.core.security`.

### 3. Đăng nhập trong test

Dùng `POST /api/auth/login` (prefix `/api` theo `main.py`), không phải `/auth/login`.

```python
def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
```

---

## Ràng buộc kỹ thuật

| Ràng buộc | Nguồn |
|-----------|-------|
| Không sửa code developer (`ownership.py`, `stations.py`) | DoD Sprint 1 |
| Không sinh test giả cho chức năng không tồn tại | QA Convention |
| Integration test đặt ở `backend/app/tests/integration/` | 01_CODEBASE_MAP |
| Dùng `caplog` để assert log — không mock logger | 02_CODING_STANDARDS |
| `raise_server_exceptions=False` trong `TestClient` để test không bị crash khi 403/500 | conftest convention |

---

## Tiêu chí hoàn thành (AC)

- `pytest app/tests/integration/test_ownership_access.py -v` xanh toàn bộ.
- `pytest app/tests/` xanh — không làm hỏng các test unit hiện có.
- File `tests/T-07_integration_test_results.md` ghi lại output pytest đầy đủ.
