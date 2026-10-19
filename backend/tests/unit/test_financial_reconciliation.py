"""SCRUM-85: reconcile tariff amounts, invoices, and actual wallet debits."""

import csv
from datetime import UTC, datetime
from io import StringIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.charge_point import ChargePoint
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.station_tariff import StationTariff, TariffBand
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.ocpp.handlers.start_transaction import handle_start_transaction
from app.ocpp.handlers.stop_transaction import handle_stop_transaction
from app.services.billing import finalize_session_billing
from app.services.reconciliation_periods import FinancialPeriodLocked


@pytest.fixture
def financial_env(db_session):
    previous_overrides = dict(app.dependency_overrides)
    owner = User(id=8501, email="fin-owner@example.test", password_hash="h", full_name="Owner", is_active=True)
    driver = User(id=8502, email="fin-driver@example.test", password_hash="h", full_name="Driver", is_active=True)
    accountant = User(id=8503, email="fin-accountant@example.test", password_hash="h", full_name="Accountant", is_active=True)
    owner.roles = [Role(id=8501, name="station_owner")]
    driver.roles = [Role(id=8502, name="driver")]
    accountant.roles = [Role(id=8503, name="accountant")]
    station = Station(id=8501, name="Financial station", owner_id=owner.id, status="active")
    point = ChargePoint(id=8501, code="FIN-CP-01", station_id=station.id, status="Available")
    tariff = StationTariff(
        id=8501,
        station_id=station.id,
        name="Test tariff",
        timezone_name="Asia/Ho_Chi_Minh",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
        bands=[TariffBand(label="All day", start_minute=0, end_minute=1440, price_vnd_per_kwh=4000)],
        is_demo=False,
    )
    sessions = [
        ChargingSession(
            id=8501 + index,
            station_id=station.id,
            station_name=station.name,
            charge_point_code=point.code,
            connector_number=index,
            user_id=driver.id,
            started_at=datetime(2026, 10, 5, 3, 0, tzinfo=UTC).replace(tzinfo=None),
            ended_at=datetime(2026, 10, 5, 4, 0, tzinfo=UTC).replace(tzinfo=None),
            status="completed",
            meter_start_wh=0,
            meter_stop_wh=energy_wh,
            energy_kwh=energy_wh / 1000,
            is_demo=False,
        )
        for index, energy_wh in enumerate((2000, 1500, 1000), start=1)
    ]
    db_session.add_all([owner, driver, accountant, *owner.roles, *driver.roles, *accountant.roles, station, point, tariff, *sessions])
    db_session.flush()
    db_session.add_all([
        ChargingInvoice(
            id=8501,
            session_id=sessions[0].id,
            tariff_id=tariff.id,
            total_vnd=9000,
            segments=[{"kind": "energy", "amount_vnd": 9000}],
            is_demo=False,
        ),
        ChargingInvoice(
            id=8502,
            session_id=sessions[2].id,
            tariff_id=tariff.id,
            total_vnd=4000,
            segments=[{"kind": "energy", "amount_vnd": 4000}],
            is_demo=False,
        ),
        WalletLedgerEntry(
            user_id=driver.id,
            entry_type="session_charge",
            amount_vnd=-8500,
            idempotency_key="session_charge:8502",
            reference_type="session",
            reference_id=sessions[0].id,
            description="Charging session",
        ),
    ])
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=accountant.id,
        email=accountant.email,
        full_name=accountant.full_name,
        roles=accountant.roles,
    )
    yield {
        "owner": owner,
        "driver": driver,
        "accountant": accountant,
        "station": station,
        "sessions": sessions,
        "db": db_session,
    }
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_financial_reconciliation_reports_real_tariff_invoice_and_ledger_differences(financial_env):
    response = TestClient(app).get(
        "/api/reconciliation/financial",
        params={"from_date": "2026-10-05", "to_date": "2026-10-05", "station_id": 8501},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["summary"] == {
        "total_kwh": 4.5,
        "total_expected_vnd": 18000,
        "total_invoiced_vnd": 13000,
        "total_collected_vnd": 8500,
        "total_difference_vnd": 10500,
        "total_invoice_difference_vnd": 1000,
        "review_count": 3,
    }
    rows = {row["session_id"]: row for row in report["rows"]}
    assert rows[8502]["issues"] == ["amount_mismatch", "collection_mismatch"]
    assert rows[8503]["issues"] == ["missing_invoice"]
    assert rows[8504]["issues"] == ["missing_ledger"]
    assert rows[8503]["expected_vnd"] == 6000
    assert rows[8503]["invoiced_vnd"] is None
    assert rows[8503]["collected_vnd"] == 0


def test_financial_reconciliation_csv_uses_same_filters_and_summary(financial_env):
    client = TestClient(app)
    params = {
        "from_date": "2026-10-05", "to_date": "2026-10-05", "station_id": 8501,
        "status": "missing_invoice",
    }
    report = client.get("/api/reconciliation/financial", params=params).json()
    response = client.get("/api/reconciliation/financial.csv", params=params)

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0]["row_type"] == "TOTAL"
    assert rows[0]["expected_vnd"] == str(report["summary"]["total_expected_vnd"])
    assert rows[0]["collected_vnd"] == str(report["summary"]["total_collected_vnd"])
    assert [row["session_id"] for row in rows[1:]] == [str(item["session_id"]) for item in report["rows"]]
    assert rows[1]["issues"] == "missing_invoice"


def test_financial_reconciliation_filters_station_point_and_issue(financial_env):
    response = TestClient(app).get(
        "/api/reconciliation/financial",
        params={
            "from_date": "2026-10-05",
            "to_date": "2026-10-05",
            "station_id": 8501,
            "charge_point_code": "FIN-CP-01",
            "status": "missing_invoice",
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert [row["session_id"] for row in report["rows"]] == [8503]
    assert report["summary"]["total_expected_vnd"] == 6000
    assert report["summary"]["total_collected_vnd"] == 0


def test_financial_reconciliation_rejects_invalid_range_and_non_accountants(financial_env):
    client = TestClient(app)
    invalid = client.get(
        "/api/reconciliation/financial",
        params={"from_date": "2026-10-06", "to_date": "2026-10-05"},
    )
    assert invalid.status_code == 422

    driver = financial_env["driver"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=driver.id,
        full_name=driver.full_name,
        roles=driver.roles,
    )
    forbidden = client.get(
        "/api/reconciliation/financial",
        params={"from_date": "2026-10-05", "to_date": "2026-10-05"},
    )
    assert forbidden.status_code == 403


def test_station_owner_report_is_scoped_to_owned_stations(financial_env):
    owner = financial_env["owner"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=owner.id,
        full_name=owner.full_name,
        email=owner.email,
        roles=owner.roles,
    )
    client = TestClient(app)
    page = client.get("/sessions/financial-reconciliation")
    assert page.status_code == 200
    report = client.get(
        "/api/reconciliation/financial",
        params={"from_date": "2026-10-05", "to_date": "2026-10-05"},
    )
    assert report.status_code == 200
    assert {station["id"] for station in report.json()["filters"]["stations"]} == {8501}
    assert {row["station_id"] for row in report.json()["rows"]} == {8501}
    forbidden = client.get(
        "/api/reconciliation/financial",
        params={
            "from_date": "2026-10-05",
            "to_date": "2026-10-05",
            "station_id": 9999,
        },
    )
    assert forbidden.status_code == 403


def _add_clean_station_period(financial_env):
    db = financial_env["db"]
    owner = financial_env["owner"]
    driver = financial_env["driver"]
    station = Station(id=8510, name="Lock station", owner_id=owner.id, status="active")
    point = ChargePoint(id=8510, code="LOCK-CP-01", station_id=station.id, status="online")
    tariff = StationTariff(
        id=8510,
        station_id=station.id,
        name="Lock tariff",
        timezone_name="Asia/Ho_Chi_Minh",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
        bands=[TariffBand(label="All day", start_minute=0, end_minute=1440, price_vnd_per_kwh=4000)],
        is_demo=False,
    )
    session = ChargingSession(
        id=8510,
        charge_point_id=point.id,
        charge_point_code=point.code,
        station_id=station.id,
        station_name=station.name,
        connector_number=1,
        user_id=driver.id,
        started_at=datetime(2026, 10, 5, 3, tzinfo=UTC).replace(tzinfo=None),
        ended_at=datetime(2026, 10, 5, 4, tzinfo=UTC).replace(tzinfo=None),
        status="completed",
        meter_start_wh=0,
        meter_stop_wh=1000,
        energy_kwh=1,
        is_demo=False,
    )
    db.add_all([station, point, tariff, session])
    db.flush()
    db.add_all([
        ChargingInvoice(
            id=8510,
            session_id=session.id,
            tariff_id=tariff.id,
            total_vnd=4000,
            segments=[{"kind": "energy", "amount_vnd": 4000}],
            is_demo=False,
        ),
        WalletLedgerEntry(
            user_id=driver.id,
            entry_type="session_charge",
            amount_vnd=-4000,
            idempotency_key="session_charge:8510",
            reference_type="session",
            reference_id=session.id,
            description="Charging session",
        ),
    ])
    db.commit()
    return station, point, session


def test_reconciliation_period_lock_saves_snapshot_idempotently_and_audits(financial_env):
    station, _, _ = _add_clean_station_period(financial_env)
    client = TestClient(app)
    payload = {"station_id": station.id, "from_date": "2026-10-05", "to_date": "2026-10-05"}

    first = client.post("/api/reconciliation/financial/lock", json=payload)
    assert first.status_code == 200
    locked = first.json()
    assert locked["period_state"] == "locked"
    assert locked["already_locked"] is False
    assert locked["summary"]["total_expected_vnd"] == 4000
    assert locked["summary"]["total_collected_vnd"] == 4000

    second = client.post("/api/reconciliation/financial/lock", json=payload)
    assert second.status_code == 200
    repeated = second.json()
    assert repeated["already_locked"] is True
    assert repeated["locked_at"] == locked["locked_at"]
    assert repeated["rows"] == locked["rows"]

    report = client.get(
        "/api/reconciliation/financial",
        params={"from_date": "2026-10-05", "to_date": "2026-10-05", "station_id": station.id},
    )
    assert report.json()["period_state"] == "locked"
    assert report.json()["rows"] == locked["rows"]
    exported = client.get(
        "/api/reconciliation/financial.csv",
        params={"from_date": "2026-10-05", "to_date": "2026-10-05", "station_id": station.id},
    )
    csv_rows = list(csv.DictReader(StringIO(exported.content.decode("utf-8-sig"))))
    assert csv_rows[0]["row_type"] == "TOTAL"
    assert csv_rows[0]["expected_vnd"] == "4000"
    assert csv_rows[1]["session_id"] == str(locked["rows"][0]["session_id"])
    audit_count = financial_env["db"].query(AuditLog).filter_by(
        action="reconciliation.period_locked"
    ).count()
    assert audit_count == 1
    owner = financial_env["owner"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=owner.id, email=owner.email, full_name=owner.full_name, roles=owner.roles
    )
    owner_repeat = client.post("/api/reconciliation/financial/lock", json=payload)
    assert owner_repeat.status_code == 200
    assert owner_repeat.json()["already_locked"] is True


def test_reconciliation_period_lock_refuses_unresolved_variances(financial_env):
    response = TestClient(app).post(
        "/api/reconciliation/financial/lock",
        json={"station_id": 8501, "from_date": "2026-10-05", "to_date": "2026-10-05"},
    )
    assert response.status_code == 409
    assert "xử lý toàn bộ phiên" in response.json()["detail"]


def test_locked_period_rejects_late_ocpp_stop_and_billing_write(financial_env):
    station, point, _ = _add_clean_station_period(financial_env)
    lock = TestClient(app).post(
        "/api/reconciliation/financial/lock",
        json={"station_id": station.id, "from_date": "2026-10-05", "to_date": "2026-10-05"},
    )
    assert lock.status_code == 200
    db = financial_env["db"]
    start_response = handle_start_transaction(
        db,
        point,
        "late-start",
        {
            "connectorId": 1,
            "meterStart": 0,
            "idTag": "LATE-START",
            "timestamp": "2026-10-05T03:00:00Z",
        },
    )
    assert "SecurityError" in start_response
    assert db.query(ChargingSession).filter_by(charge_point_id=point.id).count() == 1

    active = ChargingSession(
        id=8511,
        charge_point_id=point.id,
        charge_point_code=point.code,
        station_id=station.id,
        station_name=station.name,
        connector_number=2,
        user_id=financial_env["driver"].id,
        started_at=datetime(2026, 10, 5, 3, tzinfo=UTC).replace(tzinfo=None),
        meter_start_wh=0,
        status="active",
        is_demo=False,
    )
    db.add(active)
    db.flush()
    response = handle_stop_transaction(
        db,
        point,
        "lock-stop",
        {"transactionId": active.id, "meterStop": 1000, "timestamp": "2026-10-05T04:00:00Z"},
    )
    assert "SecurityError" in response
    assert db.get(ChargingSession, active.id).ended_at is None
    assert db.query(ChargingInvoice).filter_by(session_id=active.id).count() == 0

    late = ChargingSession(
        id=8512,
        charge_point_id=point.id,
        charge_point_code=point.code,
        station_id=station.id,
        station_name=station.name,
        connector_number=3,
        user_id=financial_env["driver"].id,
        started_at=datetime(2026, 10, 5, 3, tzinfo=UTC).replace(tzinfo=None),
        ended_at=datetime(2026, 10, 5, 4, tzinfo=UTC).replace(tzinfo=None),
        meter_start_wh=0,
        meter_stop_wh=1000,
        status="completed",
        is_demo=False,
    )
    db.add(late)
    db.flush()
    with pytest.raises(FinancialPeriodLocked):
        finalize_session_billing(db, late, [])
    assert db.query(ChargingInvoice).filter_by(session_id=late.id).count() == 0
    assert db.query(WalletLedgerEntry).filter_by(reference_id=late.id).count() == 0
