# Yêu cầu thực thi Task T-07: Lọc theo quyền sở hữu ở tầng truy vấn và test 403 bằng curl

**AI Role**: Backend Engineer (FastAPI/SQLAlchemy)

---

## Ngữ cảnh (Context)

Dự án CSMS (Nền tảng vận hành trạm sạc xe điện). Tài liệu tham chiếu bắt buộc phải đọc trước khi code:
- `prompts/01_CODEBASE_MAP.md` — quy tắc vị trí file (unit test = hàm thuần, integration test = qua DB thật/TestClient)
- `prompts/02_CODING_STANDARDS.md` — quy chuẩn code, quy tắc log (không log PII, mọi logic mới phải có unit test)
- `prompts/SPRINT_1.md` — mục T-06 và T-07

**Story liên quan (S-04)**: Là chủ trạm, tôi chỉ được xem/sửa/xoá trạm của chính mình; chủ trạm khác không được đụng vào.

T-07 phụ thuộc T-06 (`backend/app/core/deps.py`). T-06 đã cung cấp sẵn cách lấy tài khoản hiện tại — **bắt buộc dùng lại**, không tạo cách lấy user mới:

```python
# backend/app/core/deps.py (đã có từ T-06)
async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # Lấy user_id từ session cookie, trả 401 nếu chưa đăng nhập/hết hạn/bị khoá
    ...

CurrentUser = Annotated[User, Depends(get_current_user)]

def require_role(*allowed_roles: str):
    # Dependency kiểm vai trò, mặc định từ chối nếu route không khai
    ...
```

Dùng `current_user: CurrentUser` trong signature của handler/route để lấy tài khoản hiện tại, thay vì tự đọc `request.session` hay tự query `User` ở nơi khác.

---

## Nhiệm vụ (Tasks)

### 1. Hàm lọc sở hữu dùng chung — `backend/app/services/ownership.py`

Viết đúng **một** nơi chứa điều kiện `owner_id` (NFR T-07: không chép tay `owner_id == current_user.id` rải rác trong router). Cung cấp 2 hàm công khai:

- `filter_by_owner(query, user_id: int, role_names: list[str])`
  Thêm `WHERE owner_id = user_id` vào một query/`select(Station)` bất kỳ. Nếu `"admin"` nằm trong `role_names` thì bỏ qua điều kiện lọc (admin thấy mọi trạm). Dùng cho các endpoint `list` (nhiều bản ghi).

- `check_station_access(station: Station, current_user: User) -> None`
  Dùng sau khi đã fetch một bản ghi cụ thể (`get` / `update` / `delete` một trạm theo id):
  - Admin → bỏ qua kiểm tra, return ngay.
  - Không phải admin và `station.owner_id != current_user.id` → ghi **1 dòng log WARNING** (gồm `user_id`, `station_id`, thời điểm UTC ISO-8601) rồi `raise HTTPException(403)`.
  - Không log kèm PII ngoài `user_id`/`station_id` (02_CODING_STANDARDS #2).

Mọi route trong `backend/app/routers/stations.py` (list/get/update/delete) chỉ được gọi 1 trong 2 hàm này để áp điều kiện sở hữu — không tự viết so sánh `owner_id` ở router.

### 2. Test tự động phủ ca 403 — `backend/app/tests/integration/test_ownership_access.py` (mới)

AC yêu cầu: *"Chủ trạm A gọi API trạm của B bằng curl nhận 403 và có một dòng nhật ký; test tự động phủ ca này"*. Bổ sung integration test dùng `TestClient` + fixture `two_owners_with_stations` đã có sẵn trong `conftest.py`:

- Đăng nhập bằng `owner_a` (`POST /api/auth/login`), lấy session cookie.
- Gọi `GET /api/stations/{station_b.id}` → assert status `403`.
- Gọi `PUT /api/stations/{station_b.id}` và `DELETE /api/stations/{station_b.id}` → cũng assert `403`.
- Dùng `caplog` (pytest) để assert có đúng 1 dòng log mức `WARNING` chứa `user_id` của owner_a và `station_id` của station_b.
- Thêm 1 case dương: `owner_a` gọi `GET /api/stations/{station_a.id}` → assert `200`.

Không sửa test unit hiện có ở `tests/unit/test_ownership.py`.

### 3. Kịch bản curl tái hiện thủ công

Viết kèm trong docstring đầu file test và trong `README.md`:

```bash
# 1. Đăng nhập bằng Owner A, lưu cookie phiên
curl -c cookies_a.txt -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ownerA@example.com","password":"TestPass123!"}'

# 2. Đăng nhập Owner B để lấy station_id của trạm B
curl -c cookies_b.txt -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ownerB@example.com","password":"TestPass123!"}'
curl -b cookies_b.txt http://localhost:8000/api/stations

# 3. Owner A gọi GET trạm của B -> phải nhận 403
curl -b cookies_a.txt -i http://localhost:8000/api/stations/<ID_TRAM_B>
# Log kỳ vọng (stdout/uvicorn, mức WARNING, 1 dòng):
#   ACCESS_DENIED user_id=<A_ID> station_id=<ID_TRAM_B> at=<ISO8601_UTC>

# 4. Owner A gọi PUT trạm của B -> 403
curl -b cookies_a.txt -i -X PUT http://localhost:8000/api/stations/<ID_TRAM_B> \
  -H "Content-Type: application/json" -d '{"name":"Ten bi chiem"}'

# 5. Owner A gọi DELETE trạm của B -> 403
curl -b cookies_a.txt -i -X DELETE http://localhost:8000/api/stations/<ID_TRAM_B>

# 6. Owner A gọi GET trạm của chính mình -> 200
curl -b cookies_a.txt -i http://localhost:8000/api/stations/<ID_TRAM_A>
```

---

## Ràng buộc kỹ thuật (từ AC/NFR trong SPRINT_1.md)

| Ràng buộc | Nguồn |
|-----------|-------|
| Điều kiện sở hữu nằm trong đúng một hàm dùng chung, không chép tay vào từng truy vấn | T-07 NFR |
| Lấy tài khoản hiện tại phải dùng lại `get_current_user`/`CurrentUser` từ T-06 | T-07 Deps: T-06 |
| Chủ trạm A gọi API trạm của B → 403 + đúng 1 dòng log; phải có test tự động phủ ca này | T-07 AC |
| Không log mật khẩu/token/PII, chỉ log id liên quan | 02_CODING_STANDARDS #2 |
| Mọi logic nghiệp vụ mới phải có unit/integration test kèm theo | 02_CODING_STANDARDS |
| Unit test (hàm thuần) đặt ở `tests/unit/`, test qua DB thật/HTTP đặt ở `tests/integration/` | 01_CODEBASE_MAP |

---

## Tiêu chí hoàn thành (AC)

- `backend/app/services/ownership.py` chỉ có một hàm chứa điều kiện `owner_id`, được `stations.py` gọi lại ở cả 4 route (list/get/update/delete).
- Test tích hợp mới: gọi `GET/PUT/DELETE /api/stations/{id}` bằng chủ trạm A trỏ vào trạm của B → 403, có assert bắt được đúng 1 dòng log WARNING.
- Test dương: chủ trạm A gọi vào trạm của chính A → 200 (không lọc nhầm).
- `pytest` chạy xanh toàn bộ `backend/app/tests/` (cả unit lẫn integration mới thêm).
- Có hướng dẫn curl tái hiện thủ công đúng như AC mô tả.
