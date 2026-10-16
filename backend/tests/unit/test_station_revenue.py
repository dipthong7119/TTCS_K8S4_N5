"""SCRUM-84 / SCRUM-253: Station revenue report API and frontend route tests."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
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


@pytest.fixture
def revenue_env(db_session) -> Generator[dict, None, None]:
    previous_overrides = dict(app.dependency_overrides)

    def override_get_db():
        yield db_session

    owner1 = User(id=8401, email="owner1@example.test", password_hash="h", full_name="Owner One", is_active=True)
    owner2 = User(id=8402, email="owner2@example.test", password_hash="h", full_name="Owner Two", is_active=True)
    driver = User(id=8403, email="driver@example.test", password_hash="h", full_name="Driver User", is_active=True)
    admin = User(id=8404, email="admin@example.test", password_hash="h", full_name="Admin User", is_active=True)

    role_owner = Role(id=8401, name="station_owner")
    role_driver = Role(id=8402, name="driver")
    role_admin = Role(id=8403, name="admin")

    owner1.roles = [role_owner]
    owner2.roles = [role_owner]
    driver.roles = [role_driver]
    admin.roles = [role_admin]

    db_session.add_all([owner1, owner2, driver, admin, role_owner, role_driver, role_admin])
    db_session.flush()

    st1 = Station(id=8401, name="Owner 1 Station", owner_id=owner1.id, status="active")
    st2 = Station(id=8402, name="Owner 2 Station", owner_id=owner2.id, status="active")
    db_session.add_all([st1, st2])
    db_session.flush()

    tariff = StationTariff(
        id=8401,
        station_id=st1.id,
        name="Standard",
        timezone_name="Asia/Ho_Chi_Minh",
        effective_from=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30),
        bands=[TariffBand(label="Cả ngày", start_minute=0, end_minute=1440, price_vnd_per_kwh=4000)],
        is_demo=False,
    )
    db_session.add(tariff)
    db_session.flush()

    cp1 = ChargePoint(id=8401, code="CP-8401", station_id=st1.id, status="Available")
    db_session.add(cp1)
    db_session.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    sess = ChargingSession(
        id=8401,
        station_id=st1.id,
        station_name=st1.name,
        charge_point_code="CP-8401",
        connector_number=1,
        user_id=driver.id,
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        status="completed",
        energy_kwh=15.5,
        meter_start_wh=0,
        meter_stop_wh=15500,
        is_demo=False,
    )
    db_session.add(sess)
    db_session.flush()

    invoice = ChargingInvoice(
        id=8401,
        session_id=sess.id,
        tariff_id=tariff.id,
        total_vnd=62000,
        is_demo=False,
        segments=[{"kind": "energy", "amount_vnd": 62000}],
    )
    db_session.add(invoice)
    db_session.commit()

    app.dependency_overrides[get_db] = override_get_db

    yield {
        "owner1": owner1,
        "owner2": owner2,
        "driver": driver,
        "admin": admin,
        "st1": st1,
        "st2": st2,
    }

    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_station_owner_can_get_revenue_for_own_station(revenue_env):
    owner = revenue_env["owner1"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=owner.id, roles=owner.roles, full_name=owner.full_name
    )
    client = TestClient(app)
    res = client.get("/api/stations/8401/revenue")
    assert res.status_code == 200
    data = res.json()
    assert data["station_id"] == 8401
    assert data["station_name"] == "Owner 1 Station"
    assert data["session_count"] == 1
    assert data["total_kwh"] == 15.5
    assert data["revenue_vnd"] == 62000
    assert len(data["charge_points"]) == 1
    assert data["charge_points"][0]["charge_point_code"] == "CP-8401"
    assert data["charge_points"][0]["revenue_vnd"] == 62000


def test_station_owner_forbidden_from_other_owner_revenue(revenue_env):
    owner2 = revenue_env["owner2"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=owner2.id, roles=owner2.roles, full_name=owner2.full_name
    )
    client = TestClient(app)
    res = client.get("/api/stations/8401/revenue")
    assert res.status_code == 403


def test_revenue_api_rejects_inverted_date_range(revenue_env):
    owner = revenue_env["owner1"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=owner.id, roles=owner.roles, full_name=owner.full_name
    )
    client = TestClient(app)
    res = client.get("/api/stations/8401/revenue?start_date=2026-10-20&end_date=2026-10-10")
    assert res.status_code == 422
    assert "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc" in res.json()["detail"]


def test_revenue_page_permissions_and_station_filtering(revenue_env):
    owner1 = revenue_env["owner1"]
    driver = revenue_env["driver"]
    admin = revenue_env["admin"]

    client = TestClient(app)

    # Driver is forbidden
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=driver.id, roles=driver.roles, full_name=driver.full_name
    )
    res_driver = client.get("/stations/revenue")
    assert res_driver.status_code == 403

    # Owner 1 sees only Owner 1 Station
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=owner1.id, roles=owner1.roles, full_name=owner1.full_name
    )
    res_owner1 = client.get("/stations/revenue")
    assert res_owner1.status_code == 200
    assert "Owner 1 Station" in res_owner1.text
    assert "Owner 2 Station" not in res_owner1.text

    # Admin sees all stations
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=admin.id, roles=admin.roles, full_name=admin.full_name
    )
    res_admin = client.get("/stations/revenue")
    assert res_admin.status_code == 200
    assert "Owner 1 Station" in res_admin.text
    assert "Owner 2 Station" in res_admin.text
