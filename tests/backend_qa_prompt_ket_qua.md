# Kết quả thực thi prompt Backend QA Sprint 1

**Người thực hiện**: Tạ Như Vinh
**Vai trò**: Backend QA, Security Tester
**Branch**: TA-VINH
**Ngày thực thi**: 2026-09-25

## Tài liệu đã đối chiếu

- `prompts/01_CODEBASE_MAP.md`
- `prompts/02_CODING_STANDARDS.md`
- `prompts/03_SSD_SPEC.md`
- `prompts/SPRINT_1.md`
- `prompts/plant-sprint1.md`
- Source Backend hiện có trong `backend/`

## File đã sinh

| File | Mục đích |
| --- | --- |
| `tests/conftest.py` | Database SQLite cô lập, TestClient và factory tạo user |
| `tests/test_migrations.py` | Test migration, seed role, email unique và tài khoản demo |
| `tests/test_auth.py` | Test đăng nhập, khóa tạm, cookie và giới hạn theo IP |
| `tests/test_health.py` | Test contract của endpoint health check |
| `tests/backend_test_results.md` | Báo cáo kết quả chạy pytest và các blocker |

## Phạm vi đã thực hiện

- T-04 / SCRUM-12: đã tạo test cho migration và database constraint.
- T-05 / SCRUM-13: đã tạo test cho SSD-1 và login protection.
- T-03 / SCRUM-101: đã đối chiếu health check contract hiện có.

## Phạm vi bị chặn

- SCRUM-102 / T-06: `backend/app/core/deps.py` chưa có trên `main`.
- SCRUM-103 / T-07: `backend/app/services/ownership.py` và API station chưa có.
- K-01: OCPP simulator và WebSocket gateway chưa có.

Không sinh test giả cho các chức năng chưa tồn tại và không sửa code developer.
Kết quả chạy thực tế được ghi riêng trong `backend_test_results.md`.
