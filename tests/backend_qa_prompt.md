# Yeu cau thuc thi Backend QA Sprint 1

**Nguoi thuc hien**: Ta Nhu Vinh
**Vai tro**: Backend QA, Security Tester
**Branch**: TA-VINH
**Ngay**: 2026-09-25

## Tai lieu bat buoc doc truoc

Truoc khi viet test, phai doc va doi chieu day du cac file:

1. `prompts/01_CODEBASE_MAP.md`
2. `prompts/02_CODING_STANDARDS.md`
3. `prompts/03_SSD_SPEC.md`
4. `prompts/SPRINT_1.md`
5. `prompts/plant-sprint1.md`

Phai kiem tra source hien tai trong `backend/`, khong tu suy dien endpoint hoac
chuc nang chua ton tai. Theo quy trinh ban giao cua truong nhom, toan bo artifact
QA trong yeu cau nay dat tai thu muc `tests/` o root, ngang hang voi `backend/`
va `frontend/`. Khong sua code cua developer.

## Nhiem vu

1. Tao fixture pytest dung SQLite rieng, khong doc/ghi `backend/csms.db`.
2. Override FastAPI dependency `get_db` de API test dung database test.
3. Kiem thu T-04 / SCRUM-12:
   - Alembic migration chay tien den `head` va chay lui ve `base`.
   - Seed co dung 5 role: driver, station_owner, operator, accountant, admin.
   - `users.email` co rang buoc unique.
   - Tai khoan demo seed phai xac thuc duoc bang mat khau cong bo trong README.
4. Kiem thu T-05 / SCRUM-13 va SSD-1:
   - Sai email va sai mat khau tra cung mot loi chung.
   - Lan sai thu 6 bi khoa 15 phut.
   - Nhap dung mat khau trong luc khoa van bi tu choi.
   - Trang thai khoa con sau khi tao lai TestClient.
   - Dang nhap thanh cong tao cookie HttpOnly va reset bo dem sai.
   - Bao ve dang nhap sai theo tai khoan va theo IP.
5. Kiem thu endpoint `/health` theo contract test hien co.
6. Chay toan bo test, khong sua assertion de chieu theo code dang loi.
7. Ghi ket qua pass/fail va blocker vao file bao cao trong `tests/`.

## Rang buoc

- Dung `pytest`, FastAPI `TestClient`, SQLAlchemy va Alembic da co trong du an.
- Khong them package trung chuc nang.
- Khong hardcode secret va khong log mat khau/token.
- Moi file test chi kiem thu mot nhom hanh vi.
- SCRUM-102, SCRUM-103 va K-01 chi viet test khi source tuong ung da co tren
  `main`; neu chua co thi ghi ro la blocked, khong gia lap code developer.
- Test fail do san pham la ket qua QA hop le va phai duoc ghi vao bao cao.

## Dau ra yeu cau

```text
tests/
|-- backend_qa_prompt.md
|-- backend_qa_prompt_ket_qua.md
|-- backend_test_results.md
|-- conftest.py
|-- test_auth.py
|-- test_health.py
`-- test_migrations.py
```

## Tieu chi hoan thanh

- Test khong lam thay doi database that.
- Test code vuot qua `ruff check tests`.
- Co output pytest thuc te trong file bao cao.
- Moi test fail co ket qua mong doi, ket qua thuc te va vi tri source lien quan.
- Khong sua file ngoai thu muc root `tests/`.
