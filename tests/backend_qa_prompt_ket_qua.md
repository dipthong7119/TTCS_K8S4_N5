# Ket qua thuc thi prompt Backend QA Sprint 1

**Nguoi thuc hien**: Ta Nhu Vinh
**Vai tro**: Backend QA, Security Tester
**Branch**: TA-VINH
**Ngay thuc thi**: 2026-09-25

## Tai lieu da doi chieu

- `prompts/01_CODEBASE_MAP.md`
- `prompts/02_CODING_STANDARDS.md`
- `prompts/03_SSD_SPEC.md`
- `prompts/SPRINT_1.md`
- `prompts/plant-sprint1.md`
- Source Backend hien co trong `backend/`

## File da sinh

| File | Muc dich |
| --- | --- |
| `tests/conftest.py` | Database SQLite co lap, TestClient va factory tao user |
| `tests/test_migrations.py` | Test migration, seed role, email unique va tai khoan demo |
| `tests/test_auth.py` | Test dang nhap, khoa tam, cookie va gioi han theo IP |
| `tests/test_health.py` | Test contract cua endpoint health check |
| `tests/backend_test_results.md` | Bao cao ket qua chay pytest va cac blocker |

## Pham vi da thuc hien

- T-04 / SCRUM-12: da tao test cho migration va database constraint.
- T-05 / SCRUM-13: da tao test cho SSD-1 va login protection.
- T-03 / SCRUM-101: da doi chieu health check contract hien co.

## Pham vi bi chan

- SCRUM-102 / T-06: `backend/app/core/deps.py` chua co tren `main`.
- SCRUM-103 / T-07: `backend/app/services/ownership.py` va API station chua co.
- K-01: OCPP simulator va WebSocket gateway chua co.

Khong sinh test gia cho cac chuc nang chua ton tai va khong sua code developer.
Ket qua chay thuc te duoc ghi rieng trong `backend_test_results.md`.
