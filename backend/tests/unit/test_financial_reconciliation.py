"""SCRUM-85: reconcile tariff amounts, invoices, and actual wallet debits."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.charge_point import ChargePoint
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.station_tariff import StationTariff, TariffBand
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry


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
    yield {"owner": owner, "driver": driver, "accountant": accountant, "station": station, "sessions": sessions}
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
