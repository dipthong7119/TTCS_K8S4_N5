"""SCRUM-66 / S-33: expose saved invoice detail with session ownership checks."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.station_tariff import StationTariff
from app.models.user import Role, User


def _utc_naive(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC).replace(tzinfo=None)


@pytest.fixture
def invoice_api(db_session):
    role = Role(name="driver")
    driver = User(
        id=1,
        email="invoice-driver@example.test",
        password_hash="test-hash",
        full_name="Invoice Driver",
        is_active=True,
        roles=[role],
    )
    other_driver = User(
        id=2,
        email="other-invoice-driver@example.test",
        password_hash="test-hash",
        full_name="Other Driver",
        is_active=True,
        roles=[role],
    )
    station = Station(id=1, name="Invoice station", owner_id=driver.id)
    tariff = StationTariff(
        id=1,
        station_id=station.id,
        name="Invoice tariff",
        timezone_name="Asia/Ho_Chi_Minh",
        effective_from=_utc_naive(2026, 10, 1),
    )
    session = ChargingSession(
        id=100,
        charge_point_code="CP-INVOICE",
        station_id=station.id,
        station_name=station.name,
        connector_number=1,
        user_id=driver.id,
        meter_start_wh=10_000,
        meter_stop_wh=12_000,
        started_at=_utc_naive(2026, 10, 10, 2),
        ended_at=_utc_naive(2026, 10, 10, 3),
        status="completed",
    )
    db_session.add_all([driver, other_driver, station, tariff, session])
    db_session.flush()
    invoice = ChargingInvoice(
        session_id=session.id,
        tariff_id=tariff.id,
        total_vnd=8_000,
        segments=[
            {
                "from": "2026-10-10T09:00:00+07:00",
                "to": "2026-10-10T10:00:00+07:00",
                "service_date": "2026-10-10",
                "band": "Tiêu chuẩn",
                "energy_kwh": "2.000000",
                "price_vnd_per_kwh": 4_000,
                "amount_vnd": 8_000,
                "tariff_id": tariff.id,
            }
        ],
        rounding_rule="Làm tròn HALF_UP đến đồng trên từng khung giá.",
        calculation_version="time-band-v1",
        is_demo=False,
    )
    pending_session = ChargingSession(
        id=101,
        charge_point_code="CP-INVOICE",
        station_id=station.id,
        station_name=station.name,
        connector_number=1,
        user_id=driver.id,
        meter_start_wh=10_000,
        meter_stop_wh=9_000,
        started_at=_utc_naive(2026, 10, 10, 4),
        ended_at=_utc_naive(2026, 10, 10, 5),
        status="needs_review",
        needs_review=True,
        review_reason="negative_kwh",
    )
    db_session.add_all([invoice, pending_session])
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: driver
    try:
        yield TestClient(app), driver, other_driver, session, pending_session, invoice
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_driver_invoice_api_returns_saved_segment_snapshot(invoice_api):
    client, _driver, _other, session, _pending, invoice = invoice_api

    response = client.get(f"/api/sessions/{session.id}/invoice")

    assert response.status_code == 200
    assert response.json() == {
        "invoice_id": invoice.id,
        "session_id": session.id,
        "status": "issued",
        "currency": "VND",
        "total_vnd": 8_000,
        "segments": invoice.segments,
        "rounding_rule": invoice.rounding_rule,
        "calculation_version": invoice.calculation_version,
        "tariff_id": invoice.tariff_id,
        "subscription_id": None,
        "package_name": None,
        "is_demo": False,
        "created_at": invoice.created_at.isoformat() + "Z",
    }


def test_invoice_api_shows_review_state_without_provisional_amount(invoice_api):
    client, _driver, _other, _session, pending_session, _invoice = invoice_api

    response = client.get(f"/api/sessions/{pending_session.id}/invoice")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": pending_session.id,
        "status": "pending_review",
        "message": "Phiên sạc đang chờ xử lý; hóa đơn chưa sẵn sàng.",
    }


def test_driver_cannot_read_another_drivers_invoice(invoice_api):
    client, _driver, other_driver, session, _pending, _invoice = invoice_api
    app.dependency_overrides[get_current_user] = lambda: other_driver

    response = client.get(f"/api/sessions/{session.id}/invoice")

    assert response.status_code == 403
