import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.id_tag import IdTag
from app.models.ocpp_message import OcppMessage
from app.models.station import Station
from app.models.user import Role, User
from app.routers.monitoring import get_monitoring_tree
from app.services.connection_manager import ConnectionManager
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    owner = User(id=1, email="owner@test.local", password_hash="hash", full_name="Owner")
    owner.roles = [Role(name="driver")]
    station = Station(id=1, name="Station", owner_id=1, status="active")
    point = ChargePoint(id=1, code="CP-1", station_id=1, status="offline")
    connector = Connector(id=1, charge_point_id=1, connector_id=1, status="unknown")
    db.add_all([owner, station, point, connector])
    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_duplicate_message_id_is_scoped_to_charge_point(db_session):
    second_point = ChargePoint(id=2, code="CP-2", station_id=1, status="offline")
    second_connector = Connector(id=2, charge_point_id=2, connector_id=1, status="unknown")
    db_session.add_all([second_point, second_connector])
    db_session.commit()

    raw_one = pack_call("reused-id", "StatusNotification", {
        "connectorId": 1, "status": "Charging", "errorCode": "NoError",
    })
    raw_two = pack_call("reused-id", "StatusNotification", {
        "connectorId": 1, "status": "Available", "errorCode": "NoError",
    })

    first_response = handle_ocpp_message(db_session, "CP-1", raw_one)
    second_response = handle_ocpp_message(db_session, "CP-2", raw_two)

    assert parse_message(first_response)[3] == {}
    assert parse_message(second_response)[3] == {}
    assert db_session.query(OcppMessage).count() == 2
    assert db_session.query(Connector).filter_by(charge_point_id=2).one().status == "rảnh"


def test_authorize_blocks_driver_when_station_is_paused(db_session):
    db_session.add(IdTag(id_tag="DRIVER-VALID", user_id=1, is_blocked=False))
    db_session.query(Station).filter_by(id=1).one().status = "inactive"
    db_session.commit()

    response = handle_ocpp_message(
        db_session,
        "CP-1",
        pack_call("authorize-paused", "Authorize", {"idTag": "DRIVER-VALID"}),
    )

    assert parse_message(response)[3]["idTagInfo"]["status"] == "Blocked"


def test_invalid_tag_is_logged_only_with_last_four_characters(db_session, caplog):
    with caplog.at_level("WARNING"):
        response = handle_ocpp_message(
            db_session,
            "CP-1",
            pack_call("authorize-unknown", "Authorize", {"idTag": "PRIVATE-TAG-1234"}),
        )

    assert parse_message(response)[3]["idTagInfo"]["status"] == "Invalid"
    assert "1234" in caplog.text
    assert "PRIVATE-TAG-1234" not in caplog.text


def test_unknown_connector_status_is_preserved_separately(db_session):
    response = handle_ocpp_message(
        db_session,
        "CP-1",
        pack_call("unknown-status", "StatusNotification", {
            "connectorId": 1, "status": "VendorSpecificState", "errorCode": "NoError",
        }),
    )

    connector = db_session.query(Connector).filter_by(id=1).one()
    assert parse_message(response)[0] == 3
    assert connector.status == "unknown"
    assert connector.ocpp_status == "VendorSpecificState"


def test_boot_uses_configured_heartbeat_interval(db_session, monkeypatch):
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 17, raising=False)

    response = handle_ocpp_message(
        db_session,
        "CP-1",
        pack_call("boot-config", "BootNotification", {}),
    )

    assert parse_message(response)[3]["interval"] == 17


def test_monitoring_derives_offline_and_unknown_connectors_from_last_seen(db_session, monkeypatch):
    point = db_session.query(ChargePoint).filter_by(id=1).one()
    point.status = "online"
    point.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=20)
    connector = db_session.query(Connector).filter_by(id=1).one()
    connector.status = "bận"
    db_session.commit()
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 5, raising=False)

    user = SimpleNamespace(id=1, roles=[SimpleNamespace(name="admin")])
    result = asyncio.run(get_monitoring_tree(user, db_session))

    point_data = result[0]["charge_points"][0]
    assert point_data["status"] == "offline"
    assert point_data["connectors"][0]["status"] == "unknown"


def test_connection_manager_correlates_remote_call_result():
    from unittest.mock import AsyncMock

    manager = ConnectionManager()
    websocket = AsyncMock()

    async def exercise():
        await manager.connect("CP-1", websocket)
        pending = asyncio.create_task(
            manager.send_call("CP-1", "Reset", {"type": "Soft"}, timeout=1)
        )
        await asyncio.sleep(0)
        frame = json.loads(websocket.send_text.await_args.args[0])
        assert frame[0] == 2
        assert frame[2] == "Reset"
        await manager.resolve_call_result("CP-1", frame[1], {"status": "Accepted"})
        return await pending

    result = asyncio.run(exercise())
    assert result == {"status": "Accepted"}


def test_connection_manager_cleans_pending_call_on_timeout():
    from unittest.mock import AsyncMock

    manager = ConnectionManager()
    websocket = AsyncMock()

    async def exercise():
        await manager.connect("CP-1", websocket)
        with pytest.raises(asyncio.TimeoutError):
            await manager.send_call("CP-1", "Reset", {"type": "Soft"}, timeout=0.001)
        assert manager.pending_calls == {}

    asyncio.run(exercise())
