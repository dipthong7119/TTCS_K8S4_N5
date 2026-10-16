"""SCRUM-80/81/82: station limits and dynamic equal-share charging profiles."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.user import User
from app.routers.power_capacity import update_power_capacity
from app.schemas.power_capacity import (
    ConnectorPowerCapacityInput,
    StationPowerCapacityUpdate,
)
from app.services import power_allocation
from app.services.power_allocation import (
    calculate_equal_share_limits,
    rebalance_station_once,
)


def test_equal_shares_are_whole_watts_and_never_exceed_station_limit():
    limits = calculate_equal_share_limits(
        Decimal(100),
        [(1, Decimal(120)), (2, Decimal(120)), (3, Decimal(120))],
    )

    assert limits == {1: 33333, 2: 33333, 3: 33333}
    assert sum(limits.values()) <= 100_000


def _make_station(db, station_limit_kw: str, ratings_kw: list[str]):
    owner = User(email="power-owner@test", password_hash="x", full_name="Owner")
    db.add(owner)
    db.flush()
    station = Station(
        name="Power station",
        owner_id=owner.id,
        status="active",
        power_limit_kw=Decimal(station_limit_kw),
    )
    db.add(station)
    db.flush()
    point = ChargePoint(code="POWER-CP", station_id=station.id, status="online")
    db.add(point)
    db.flush()

    connectors = []
    sessions = []
    for connector_number, rating in enumerate(ratings_kw, start=1):
        connector = Connector(
            charge_point_id=point.id,
            connector_id=connector_number,
            status="charging",
            ocpp_status="Charging",
            rated_power_kw=Decimal(rating),
        )
        db.add(connector)
        session = ChargingSession(
            charge_point_id=point.id,
            charge_point_code=point.code,
            station_id=station.id,
            station_name=station.name,
            connector_number=connector_number,
            meter_start_wh=0,
            started_at=datetime.now(UTC).replace(tzinfo=None),
            status="active",
        )
        db.add(session)
        connectors.append(connector)
        sessions.append(session)
    db.commit()
    return station, connectors, sessions


def test_rebalance_sends_equal_profiles_and_skips_unchanged_limits(db_session):
    station, _connectors, sessions = _make_station(db_session, "100", ["80", "80"])
    calls = []

    async def send_call(code, action, payload):
        calls.append((code, action, payload))
        return {"status": "Accepted"}

    count = asyncio.run(
        rebalance_station_once(db_session, station.id, send_call=send_call)
    )
    assert count == 2
    assert [
        call[2]["csChargingProfiles"]["chargingSchedule"]["chargingSchedulePeriod"][0]["limit"]
        for call in calls
    ] == [50_000, 50_000]
    assert all(call[1] == "SetChargingProfile" for call in calls)
    assert all(
        call[2]["csChargingProfiles"]["chargingSchedule"]["chargingRateUnit"] == "W"
        for call in calls
    )
    assert sum(session.requested_power_limit_w for session in sessions) == 100_000
    assert db_session.query(AuditLog).filter_by(
        action="charging_power.profile_requested"
    ).count() == 2

    assert asyncio.run(
        rebalance_station_once(db_session, station.id, send_call=send_call)
    ) == 0
    assert len(calls) == 2
    assert db_session.query(AuditLog).filter_by(action="charging_power.profile_result").count() == 2


def test_suspended_ev_releases_share_to_remaining_session(db_session):
    station, connectors, sessions = _make_station(db_session, "100", ["80", "80"])
    sent_limits = []

    async def send_call(_code, action, payload):
        if action == "SetChargingProfile":
            limit = payload["csChargingProfiles"]["chargingSchedule"]["chargingSchedulePeriod"][0]["limit"]
            sent_limits.append((payload["connectorId"], limit))
        return {"status": "Accepted"}

    asyncio.run(rebalance_station_once(db_session, station.id, send_call=send_call))
    connectors[1].ocpp_status = "SuspendedEV"
    db_session.commit()

    count = asyncio.run(
        rebalance_station_once(db_session, station.id, send_call=send_call)
    )
    assert count == 1
    assert sent_limits[-1] == (connectors[0].connector_id, 80_000)
    assert sessions[0].requested_power_limit_w == 80_000


def test_rejected_profile_requests_remote_stop_and_records_alert(db_session):
    station, _connectors, sessions = _make_station(db_session, "20", ["80"])
    calls = []

    async def send_call(_code, action, _payload):
        calls.append(action)
        return {"status": "Rejected" if action == "SetChargingProfile" else "Accepted"}

    asyncio.run(rebalance_station_once(db_session, station.id, send_call=send_call))

    db_session.refresh(sessions[0])
    assert calls == ["SetChargingProfile", "RemoteStopTransaction"]
    assert sessions[0].remote_stop_requested_at is not None
    assert db_session.query(AuditLog).filter_by(
        action="charging_power.rejected_session_stop"
    ).one().details["outcome"] == "Accepted"


def test_owner_can_configure_kw_limits_and_see_over_subscription_warning(
    db_session, monkeypatch, caplog
):
    owner = User(email="capacity-owner@test", password_hash="x", full_name="Owner")
    db_session.add(owner)
    db_session.flush()
    station = Station(name="Capacity station", owner_id=owner.id, status="active")
    db_session.add(station)
    db_session.flush()
    point = ChargePoint(code="CAPACITY-CP", station_id=station.id, status="offline")
    db_session.add(point)
    db_session.flush()
    connector = Connector(charge_point_id=point.id, connector_id=1, status="unknown")
    db_session.add(connector)
    db_session.commit()
    monkeypatch.setattr(
        power_allocation,
        "schedule_station_rebalance",
        lambda _station_id: None,
    )
    body = StationPowerCapacityUpdate(
        power_limit_kw=Decimal(50),
        connectors=[
            ConnectorPowerCapacityInput(
                charge_point_code="CAPACITY-CP",
                connector_id=1,
                rated_power_kw=Decimal(80),
            )
        ],
    )

    response = asyncio.run(
        update_power_capacity(station.id, body, owner, db_session)
    )

    assert response["power_limit_kw"] == Decimal("50.000")
    assert response["nominal_power_kw"] == Decimal(80)
    assert response["over_subscribed"] is True
    assert connector.rated_power_kw == Decimal(80)
    assert "Station is over-subscribed" in caplog.text
