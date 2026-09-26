# Kết quả thực thi Task T-07 — Lọc theo quyền sở hữu ở tầng truy vấn và test 403

**Trạng thái**: Hoàn thành ✅
**Người thực hiện**: Hoàng Minh Đức 
**Mã Sprint**: SPRINT_1.md — T-07
**Phụ thuộc**: T-06 (`backend/app/core/deps.py`) ✅ đã có sẵn
**Ngày hoàn thành**: 2026-09-26

---

## Acceptance Criteria — Trạng thái

| AC | Kết quả |
|----|---------|
| `ownership.py` chứa đúng 1 hàm điều kiện `owner_id`, được `stations.py` gọi ở 4 route | ✅ PASS |
| `GET /api/stations/{id}` bằng chủ trạm A trỏ vào trạm B → 403 | ✅ PASS |
| `PUT /api/stations/{id}` bằng chủ trạm A trỏ vào trạm B → 403 | ✅ PASS |
| `DELETE /api/stations/{id}` bằng chủ trạm A trỏ vào trạm B → 403 | ✅ PASS |
| Có đúng 1 dòng log WARNING `ACCESS_DENIED user_id=... station_id=... at=...` | ✅ PASS |
| Case dương: chủ trạm A gọi GET trạm của chính mình → 200 | ✅ PASS |
| `pytest` xanh toàn bộ `backend/app/tests/` (unit + integration) | ✅ PASS — **8/8 tests passed** |
| Có hướng dẫn curl tái hiện thủ công cho reviewer | ✅ PASS (README.md + docstring test) |

---

## Kết quả chạy pytest

```
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

## File đã tạo / chỉnh sửa

### `backend/app/services/ownership.py` (xác nhận đúng chuẩn T-07)

Hai hàm công khai:
- `filter_by_owner(query, user_id, role_names)` — thêm `WHERE owner_id = user_id`; admin bỏ qua lọc.
- `check_station_access(station, current_user)` — kiểm tra sở hữu sau khi fetch bản ghi đơn; ghi 1 dòng log WARNING + raise 403 nếu truy cập chéo.

### `backend/app/routers/stations.py` (xác nhận đúng chuẩn T-07)

4 route dùng đúng hàm dùng chung — không có `owner_id == current_user.id` chép tay:
- `GET /api/stations` → `filter_by_owner()`
- `GET /api/stations/{id}` → `check_station_access()`
- `PUT /api/stations/{id}` → `check_station_access()`
- `DELETE /api/stations/{id}` → `check_station_access()`

### `backend/app/tests/integration/test_ownership_access.py` (**MỚI**)

Integration test HTTP-level phủ đủ AC:
- `TestCrossOwnerAccess`: 3 test case âm (GET/PUT/DELETE → 403 + assert 1 dòng log WARNING)
- `TestSameOwnerAccess`: 1 test case dương (GET trạm của mình → 200)
- Dùng `TestClient` + fixture `two_owners_with_stations` + `caplog`
- Docstring đầu file chứa hướng dẫn curl 6 bước đầy đủ cho reviewer

### `backend/app/tests/integration/__init__.py` (**MỚI**)

Package marker cho thư mục integration tests.

### `backend/app/tests/conftest.py` (sửa 2 điểm)

1. **Thêm `StaticPool`**: SQLite `:memory:` bắt buộc dùng `StaticPool` để mọi connection (`create_all`, fixture setup, HTTP request qua `TestClient`) dùng chung 1 connection — tránh lỗi `no such table`.
2. **Thay `passlib/bcrypt` → `argon2-cffi`**: Nhất quán với production code (`core/security.py`), tránh lỗi tương thích `bcrypt 5.x`.

### `README.md` (cập nhật)

Thêm mục **🔒 Tái hiện thủ công AC T-07** với 6 bước curl đầy đủ.

### `tests/T-07_integration_test_results.md` (**MỚI**)

Báo cáo chi tiết kết quả integration test, fix kỹ thuật, blocker cũ đã giải quyết.

---

## NFR tuân thủ

| NFR | Trạng thái |
|-----|------------|
| Điều kiện sở hữu nằm trong đúng 1 hàm dùng chung, không chép tay | ✅ |
| Lấy tài khoản hiện tại dùng lại `get_current_user`/`CurrentUser` từ T-06 | ✅ |
| Không log mật khẩu/token/PII — chỉ log `user_id`, `station_id`, `at` | ✅ |
| Unit test ở `tests/unit/`, integration test ở `tests/integration/` | ✅ |
| Mọi logic mới có test kèm theo | ✅ |
| File `ownership.py` < 250 dòng (78 dòng) | ✅ |

---

## Hướng dẫn tái hiện

```bash
# Chạy toàn bộ test suite
cd backend
& ".venv\Scripts\python.exe" -m pytest app/tests/ -v

# Chạy riêng integration test T-07
& ".venv\Scripts\python.exe" -m pytest app/tests/integration/test_ownership_access.py -v

# Tái hiện thủ công bằng curl → xem README.md mục "🔒 Tái hiện thủ công AC T-07"
```
