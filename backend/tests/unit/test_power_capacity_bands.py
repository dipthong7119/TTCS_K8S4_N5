"""SCRUM-83 power-band validation, ownership, allocation, and SSE coverage."""

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.station_power_band import StationPowerBand
from app.models.user import User
from app.routers import monitoring
from app.routers.power_capacity_bands import (
    create_power_capacity_band,
    delete_power_capacity_band,
    list_power_capacity_bands,
    update_power_capacity_band,
)
from app.schemas.power_capacity_band import PowerCapacityBandInput
from app.services.jobs import rebalance_scheduled_power_once
from app.services.power_allocation import rebalance_station_once
from app.services.power_capacity_bands import (
    PowerBandOverlapError,
    effective_station_power_limit_kw,
    ensure_no_power_band_overlap,
)


def _make_station(db, default_limit: str = "100"):
    owner = User(email=f"owner-{default_limit}@bands.test", password_hash="x", full_name="Owner")
    db.add(owner)
    db.flush()
    station = Station(
        name="Band station",
        owner_id=owner.id,
        status="active",
        power_limit_kw=Decimal(default_limit) if default_limit else None,
    )
    db.add(station)
    db.commit()
    return owner, station


def _add_band(db, station_id: int, start: int, end: int, limit: str) -> StationPowerBand:
    band = StationPowerBand(
        station_id=station_id,
        start_minute=start,
        end_minute=end,
        power_limit_kw=Decimal(limit),
    )
    db.add(band)
    db.commit()
    return band


def test_effective_limit_uses_multiple_bands_boundaries_and_default(db_session):
    _owner, station = _make_station(db_session)
    _add_band(db_session, station.id, 480, 1020, "80")
    _add_band(db_session, station.id, 1020, 1320, "60")

    assert effective_station_power_limit_kw(
        db_session, station.id, Decimal(100), datetime(2026, 10, 19, 9, 59, tzinfo=UTC)
    ) == Decimal("80.000")  # 16:59 at station-local time
    assert effective_station_power_limit_kw(
        db_session, station.id, Decimal(100), datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    ) == Decimal("60.000")  # start is inclusive at 17:00
    assert effective_station_power_limit_kw(
        db_session, station.id, Decimal(100), datetime(2026, 10, 19, 15, 0, tzinfo=UTC)
    ) == Decimal(100)  # end is exclusive at 22:00


def test_effective_limit_supports_overnight_band_and_no_band_fallback(db_session):
    _owner, station = _make_station(db_session)
    _add_band(db_session, station.id, 1320, 360, "40")
    _add_band(db_session, station.id, 600, 1320, "70")

    assert effective_station_power_limit_kw(
        db_session, station.id, Decimal(100), datetime(2026, 10, 19, 18, 0, tzinfo=UTC)
    ) == Decimal("40.000")  # 01:00 next local day
    assert effective_station_power_limit_kw(
        db_session, station.id, Decimal(100), datetime(2026, 10, 19, 3, 0, tzinfo=UTC)
    ) == Decimal("70.000")  # 10:00 local time
    assert effective_station_power_limit_kw(
        db_session, station.id, Decimal(100), datetime(2026, 10, 19, 0, 0, tzinfo=UTC)
    ) == Decimal(100)  # 07:00 local gap

    empty_owner, empty_station = _make_station(db_session, "75")
    assert empty_owner.id != station.owner_id
    assert effective_station_power_limit_kw(
        db_session, empty_station.id, Decimal(75), datetime(2026, 10, 19, 0, 0, tzinfo=UTC)
    ) == Decimal(75)
    assert effective_station_power_limit_kw(db_session, empty_station.id, None) is None


def test_power_band_validation_rejects_overlap_and_allows_adjacent_windows(db_session):
    _owner, station = _make_station(db_session)
    overnight = _add_band(db_session, station.id, 1320, 360, "40")

    with pytest.raises(PowerBandOverlapError):
        ensure_no_power_band_overlap(db_session, station.id, 300, 420)
    ensure_no_power_band_overlap(db_session, station.id, 360, 600)
    ensure_no_power_band_overlap(
        db_session, station.id, 1320, 360, exclude_band_id=overnight.id
    )
    with pytest.raises(ValueError, match="không được trùng nhau"):
        ensure_no_power_band_overlap(db_session, station.id, 600, 600)
    with pytest.raises(ValidationError):
        PowerCapacityBandInput(
            start_minute=1320, end_minute=1320, power_limit_kw=Decimal(10)
        )


def test_owner_can_manage_bands_and_cannot_access_another_owners_station(
    db_session, monkeypatch
):
    from app.routers import power_capacity_bands as band_router

    monkeypatch.setattr(band_router, "_schedule_rebalance", lambda _station_id: None)
    owner, station = _make_station(db_session)
    band = asyncio.run(
        create_power_capacity_band(
            station.id,
            PowerCapacityBandInput(
                start_minute=0, end_minute=360, power_limit_kw=Decimal(40)
            ),
            owner,
            db_session,
        )
    )
    assert band["power_limit_kw"] == Decimal("40.000")
    assert asyncio.run(list_power_capacity_bands(station.id, owner, db_session))[0]["id"] == band["id"]

    updated = asyncio.run(
        update_power_capacity_band(
            station.id,
            band["id"],
            PowerCapacityBandInput(
                start_minute=360, end_minute=600, power_limit_kw=Decimal(50)
            ),
            owner,
            db_session,
        )
    )
    assert updated["start_minute"] == 360
    assert asyncio.run(delete_power_capacity_band(station.id, band["id"], owner, db_session)) is not None

    other_owner, _other_station = _make_station(db_session, "90")
    with pytest.raises(HTTPException) as denied:
        asyncio.run(
            create_power_capacity_band(
                station.id,
                PowerCapacityBandInput(
                    start_minute=0, end_minute=60, power_limit_kw=Decimal(20)
                ),
                other_owner,
                db_session,
            )
        )
    assert denied.value.status_code == 403


def test_changing_band_rebalances_active_sessions_and_notifies_sse(
    db_session, monkeypatch
):
    from app.routers import power_capacity_bands as band_router

    monkeypatch.setattr(band_router, "_schedule_rebalance", lambda _station_id: None)
    owner, station = _make_station(db_session)
    driver = User(email="driver-bands@test", password_hash="x", full_name="Driver")
    db_session.add(driver)
    db_session.flush()
    point = ChargePoint(code="BAND-CP", station_id=station.id, status="online")
    db_session.add(point)
    db_session.flush()
    sessions = []
    for connector_number in (1, 2):
        db_session.add(
            Connector(
                charge_point_id=point.id,
                connector_id=connector_number,
                status="charging",
                ocpp_status="Charging",
                rated_power_kw=Decimal(80),
            )
        )
        session = ChargingSession(
            charge_point_id=point.id,
            charge_point_code=point.code,
            station_id=station.id,
            station_name=station.name,
            connector_number=connector_number,
            user_id=driver.id,
            meter_start_wh=0,
            started_at=datetime(2026, 10, 19, 9, 0, tzinfo=UTC).replace(tzinfo=None),
            status="active",
        )
        db_session.add(session)
        sessions.append(session)
    db_session.commit()

    owner_queue = asyncio.Queue()
    driver_queue = asyncio.Queue()
    other_queue = asyncio.Queue()
    monkeypatch.setattr(
        monitoring,
        "sse_clients",
        [
            {"queue": owner_queue, "owner_id": owner.id, "driver_id": None, "global_access": False},
            {"queue": driver_queue, "owner_id": None, "driver_id": driver.id, "global_access": False},
            {"queue": other_queue, "owner_id": 999, "driver_id": 999, "global_access": False},
        ],
    )
    band = asyncio.run(
        create_power_capacity_band(
            station.id,
            PowerCapacityBandInput(
                start_minute=0, end_minute=1440, power_limit_kw=Decimal(100)
            ),
            owner,
            db_session,
        )
    )
    now = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
    calls = []

    async def send_call(_code, action, payload):
        calls.append((action, payload))
        return {"status": "Accepted"}

    assert asyncio.run(
        rebalance_station_once(db_session, station.id, send_call=send_call, now=now)
    ) == 2
    assert sum(session.requested_power_limit_w for session in sessions) == 100_000
    while not driver_queue.empty():
        driver_queue.get_nowait()
    while not owner_queue.empty():
        owner_queue.get_nowait()

    asyncio.run(
        update_power_capacity_band(
            station.id,
            band["id"],
            PowerCapacityBandInput(
                start_minute=0, end_minute=1440, power_limit_kw=Decimal(60)
            ),
            owner,
            db_session,
        )
    )
    assert asyncio.run(
        rebalance_scheduled_power_once(db_session, now, send_call=send_call)
    ) == 2
    db_session.refresh(sessions[0])
    db_session.refresh(sessions[1])
    assert [session.requested_power_limit_w for session in sessions] == [30_000, 30_000]
    assert sum(session.requested_power_limit_w for session in sessions) <= 60_000

    driver_updates = [json.loads(driver_queue.get_nowait()["data"]) for _ in range(2)]
    owner_updates = [json.loads(owner_queue.get_nowait()["data"]) for _ in range(2)]
    assert {event["requested_power_limit_w"] for event in driver_updates} == {30_000}
    assert {event["requested_power_limit_w"] for event in owner_updates} == {30_000}
    assert other_queue.empty()
    assert asyncio.run(
        rebalance_scheduled_power_once(db_session, now, send_call=send_call)
    ) == 0
    assert len(calls) == 4
