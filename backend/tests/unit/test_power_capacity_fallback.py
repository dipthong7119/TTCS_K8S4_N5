"""Fallback behavior for schedules without a configured station default."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.station_power_band import StationPowerBand
from app.models.station_tariff import StationTariff
from app.models.user import User
from app.services.power_allocation import rebalance_station_once
from app.services.power_capacity_bands import effective_station_power_limit_kw


def test_inactive_band_without_default_restores_connector_rating(db_session):
    owner = User(email="owner-no-default@test", password_hash="x", full_name="Owner")
    db_session.add(owner)
    db_session.flush()
    station = Station(name="No default", owner_id=owner.id, status="active")
    db_session.add(station)
    db_session.flush()
    point = ChargePoint(code="NO-DEFAULT-CP", station_id=station.id, status="online")
    db_session.add(point)
    db_session.flush()
    connector = Connector(
        charge_point_id=point.id,
        connector_id=1,
        status="charging",
        ocpp_status="Charging",
        rated_power_kw=Decimal(80),
    )
    session = ChargingSession(
        charge_point_id=point.id,
        charge_point_code=point.code,
        station_id=station.id,
        station_name=station.name,
        connector_number=1,
        meter_start_wh=0,
        started_at=datetime(2026, 10, 19, 10, 0, tzinfo=UTC).replace(tzinfo=None),
        status="active",
        requested_power_limit_w=30_000,
    )
    db_session.add_all(
        [
            connector,
            session,
            StationPowerBand(
                station_id=station.id,
                start_minute=1320,
                end_minute=360,
                power_limit_kw=Decimal(40),
            ),
        ]
    )
    db_session.commit()
    calls = []

    async def send_call(_code, action, payload):
        calls.append((action, payload))
        return {"status": "Accepted"}

    # 10:00 UTC is 17:00 local, outside the 22:00–06:00 schedule.
    count = asyncio.run(
        rebalance_station_once(
            db_session,
            station.id,
            send_call=send_call,
            now=datetime(2026, 10, 19, 10, 0, tzinfo=UTC),
        )
    )

    db_session.refresh(session)
    assert count == 1
    assert session.requested_power_limit_w == 80_000
    assert calls[0][0] == "SetChargingProfile"


def test_effective_limit_uses_latest_non_demo_tariff_timezone(db_session):
    owner = User(email="owner-zone@test", password_hash="x", full_name="Owner")
    db_session.add(owner)
    db_session.flush()
    station = Station(name="Timezone", owner_id=owner.id, status="active")
    db_session.add(station)
    db_session.flush()
    db_session.add_all(
        [
            StationTariff(
                station_id=station.id,
                name="Pacific local time",
                timezone_name="America/Los_Angeles",
                effective_from=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
                is_demo=False,
            ),
            StationPowerBand(
                station_id=station.id,
                start_minute=600,
                end_minute=660,
                power_limit_kw=Decimal(50),
            ),
        ]
    )
    db_session.commit()

    assert effective_station_power_limit_kw(
        db_session,
        station.id,
        Decimal(100),
        datetime(2026, 10, 19, 17, 0, tzinfo=UTC),
    ) == Decimal("50.000")
