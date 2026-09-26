"""
tests/integration/test_ownership_access.py -- Test HTTP-level 403 khi truy cap cheo (T-07)
Tham chieu: SPRINT_1.md T-07, 02_CODING_STANDARDS.md, 01_CODEBASE_MAP.md

AC: Chu tram A goi API tram cua B nhan 403 va co mot dong nhat ky;
    test tu dong phu ca nay.

=============================================================================
HUONG DAN CURL TAI HIEN THU CONG (danh cho reviewer)
=============================================================================

Yeu cau: may chay `uvicorn app.main:app --reload --port 8000`
         (chay tu thu muc backend/)

Seed du lieu 2 chu tram truoc khi chay curl:
    python seed_data.py   # hoac chay qua docker-compose

Tai khoan va mat khau test (dung trong seed_data.py):
    Owner A: ownerA@example.com / TestPass123!
    Owner B: ownerB@example.com / TestPass123!

-----------------------------
Buoc 1: Dang nhap bang Owner A, luu cookie phien
-----------------------------
    curl -c cookies_a.txt -s -X POST http://localhost:8000/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"ownerA@example.com","password":"TestPass123!"}'

    Ket qua mong doi: HTTP 200, body JSON chua user_id va roles.

-----------------------------
Buoc 2: Dang nhap bang Owner B de lay station_id cua tram B
-----------------------------
    curl -c cookies_b.txt -s -X POST http://localhost:8000/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"ownerB@example.com","password":"TestPass123!"}'

    # Lay danh sach tram cua Owner B -> lay <ID_TRAM_B>
    curl -b cookies_b.txt -s http://localhost:8000/api/stations

-----------------------------
Buoc 3: Owner A goi GET tram cua Owner B -> phai nhan 403
-----------------------------
    curl -b cookies_a.txt -i http://localhost:8000/api/stations/<ID_TRAM_B>

    Ket qua mong doi:
      HTTP/1.1 403 Forbidden
      {"detail":"Khong co quyen truy cap tram nay"}

    Log ky vong xuat hien trong stdout/uvicorn log (1 dong, muc WARNING):
      WARNING  csms.ownership:ownership.py:XX \
        ACCESS_DENIED user_id=<A_ID> station_id=<ID_TRAM_B> at=<ISO8601_UTC>

-----------------------------
Buoc 4: Owner A goi PUT (sua) tram cua Owner B -> phai nhan 403
-----------------------------
    curl -b cookies_a.txt -i -X PUT http://localhost:8000/api/stations/<ID_TRAM_B> \
      -H "Content-Type: application/json" \
      -d '{"name":"Tram bi chiem"}'

    Ket qua mong doi: HTTP/1.1 403 Forbidden

-----------------------------
Buoc 5: Owner A goi DELETE tram cua Owner B -> phai nhan 403
-----------------------------
    curl -b cookies_a.txt -i -X DELETE http://localhost:8000/api/stations/<ID_TRAM_B>

    Ket qua mong doi: HTTP/1.1 403 Forbidden

-----------------------------
Buoc 6 (case duong): Owner A goi GET tram cua chinh minh -> phai nhan 200
-----------------------------
    # Lay <ID_TRAM_A> tu danh sach tram cua Owner A
    curl -b cookies_a.txt -s http://localhost:8000/api/stations

    curl -b cookies_a.txt -i http://localhost:8000/api/stations/<ID_TRAM_A>

    Ket qua mong doi: HTTP/1.1 200 OK, body JSON thong tin tram.

=============================================================================
"""

import logging

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper: dang nhap bang email/password, session cookie luu trong client
# ---------------------------------------------------------------------------

def _login(client: TestClient, email: str, password: str) -> None:
    """
    Thuc hien POST /api/auth/login, luu session cookie vao client.
    Raise AssertionError neu login that bai.
    """
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, (
        f"Login that bai voi {email}: {resp.status_code} {resp.text}"
    )


# ---------------------------------------------------------------------------
# Test case am: Owner A truy cap tram cua Owner B -> 403 + 1 dong log WARNING
# ---------------------------------------------------------------------------

class TestCrossOwnerAccess:
    """Kiem tra truy cap cheo giua 2 chu tram khac nhau."""

    def test_get_other_owner_station_returns_403(
        self,
        client: TestClient,
        two_owners_with_stations,
        caplog,
    ):
        """
        Owner A goi GET /api/stations/{station_b.id} -> 403
        Va co dung 1 dong log WARNING chua user_id cua A va station_id cua B.
        Khop voi AC: 'Chu tram A goi API tram cua B bang curl nhan 403 va co mot dong nhat ky'.
        """
        owner_a, station_a, owner_b, station_b = two_owners_with_stations

        _login(client, "ownerA@example.com", "TestPass123!")

        with caplog.at_level(logging.WARNING, logger="csms.ownership"):
            resp = client.get(f"/api/stations/{station_b.id}")

        assert resp.status_code == 403, (
            f"Mong doi 403, nhan duoc {resp.status_code}: {resp.text}"
        )

        # Kiem tra dung 1 dong log WARNING ACCESS_DENIED chua user_id va station_id
        warning_logs = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "ACCESS_DENIED" in r.getMessage()
        ]
        assert len(warning_logs) == 1, (
            f"Mong doi 1 dong WARNING ACCESS_DENIED, nhan duoc {len(warning_logs)}: "
            f"{[r.getMessage() for r in warning_logs]}"
        )
        log_msg = warning_logs[0].getMessage()
        assert str(owner_a.id) in log_msg, (
            f"Log phai chua user_id={owner_a.id}, thuc te: {log_msg}"
        )
        assert str(station_b.id) in log_msg, (
            f"Log phai chua station_id={station_b.id}, thuc te: {log_msg}"
        )

    def test_put_other_owner_station_returns_403(
        self,
        client: TestClient,
        two_owners_with_stations,
        caplog,
    ):
        """
        Owner A goi PUT /api/stations/{station_b.id} -> 403
        Va co dung 1 dong log WARNING.
        """
        owner_a, station_a, owner_b, station_b = two_owners_with_stations

        _login(client, "ownerA@example.com", "TestPass123!")

        with caplog.at_level(logging.WARNING, logger="csms.ownership"):
            resp = client.put(
                f"/api/stations/{station_b.id}",
                json={"name": "Ten bi sua trai phep"},
            )

        assert resp.status_code == 403, (
            f"Mong doi 403, nhan duoc {resp.status_code}: {resp.text}"
        )

        warning_logs = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "ACCESS_DENIED" in r.getMessage()
        ]
        assert len(warning_logs) == 1, (
            f"Mong doi 1 dong WARNING ACCESS_DENIED, nhan duoc {len(warning_logs)}"
        )
        log_msg = warning_logs[0].getMessage()
        assert str(owner_a.id) in log_msg
        assert str(station_b.id) in log_msg

    def test_delete_other_owner_station_returns_403(
        self,
        client: TestClient,
        two_owners_with_stations,
        caplog,
    ):
        """
        Owner A goi DELETE /api/stations/{station_b.id} -> 403
        Va co dung 1 dong log WARNING.
        """
        owner_a, station_a, owner_b, station_b = two_owners_with_stations

        _login(client, "ownerA@example.com", "TestPass123!")

        with caplog.at_level(logging.WARNING, logger="csms.ownership"):
            resp = client.delete(f"/api/stations/{station_b.id}")

        assert resp.status_code == 403, (
            f"Mong doi 403, nhan duoc {resp.status_code}: {resp.text}"
        )

        warning_logs = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "ACCESS_DENIED" in r.getMessage()
        ]
        assert len(warning_logs) == 1, (
            f"Mong doi 1 dong WARNING ACCESS_DENIED, nhan duoc {len(warning_logs)}"
        )
        log_msg = warning_logs[0].getMessage()
        assert str(owner_a.id) in log_msg
        assert str(station_b.id) in log_msg


# ---------------------------------------------------------------------------
# Test case duong: Owner A truy cap tram cua chinh minh -> 200 (khong loc nham)
# ---------------------------------------------------------------------------

class TestSameOwnerAccess:
    """Kiem tra chu tram truy cap tram cua chinh minh khong bi loc nham."""

    def test_get_own_station_returns_200(
        self,
        client: TestClient,
        two_owners_with_stations,
    ):
        """
        Owner A goi GET /api/stations/{station_a.id} -> 200.
        Xac nhan dieu kien loc so huu khong chan tram cua chinh chu so huu.
        """
        owner_a, station_a, owner_b, station_b = two_owners_with_stations

        _login(client, "ownerA@example.com", "TestPass123!")

        resp = client.get(f"/api/stations/{station_a.id}")

        assert resp.status_code == 200, (
            f"Mong doi 200 khi chu tram A truy cap tram cua minh, "
            f"nhan duoc {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert data["id"] == station_a.id
        assert data["owner_id"] == owner_a.id
