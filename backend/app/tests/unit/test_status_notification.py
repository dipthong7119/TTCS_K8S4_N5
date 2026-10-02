"""
Test cho status_mapping và handler StatusNotification (SCRUM-119).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.ocpp.status_mapping import InternalStatus, map_ocpp_status
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message

# ---------------------------------------------------------------------------
# Test module ánh xạ (pure functions)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ocpp_status,expected_internal",
    [
        ("Available", InternalStatus.IDLE),
        ("Preparing", InternalStatus.BUSY),
        ("Charging", InternalStatus.BUSY),
        ("SuspendedEV", InternalStatus.BUSY),
        ("SuspendedEVSE", InternalStatus.BUSY),
        ("Finishing", InternalStatus.BUSY),
        ("Reserved", InternalStatus.RESERVED),
        ("Unavailable", InternalStatus.FAULTED),
        ("Faulted", InternalStatus.FAULTED),
    ]
)
def test_map_ocpp_status_valid(ocpp_status, expected_internal):
    """Bảng ánh xạ: 9 trạng thái hợp lệ."""
    assert map_ocpp_status(ocpp_status) == expected_internal


@pytest.mark.parametrize(
    "strange_status",
    ["Foo", "", "available", "CHARGING", "Unknown"]
)
def test_map_ocpp_status_strange(strange_status):
    """Trạng thái lạ: không raise lỗi, trả về FAULTED để an toàn."""
    assert map_ocpp_status(strange_status) == InternalStatus.FAULTED


# ---------------------------------------------------------------------------
# Test Handler với Database (SQLite In-Memory)
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Tạo DB in-memory cho handler test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Tạo dữ liệu trạm, trụ, và 1 connector ID=1
    station = Station(id=1, name="Trạm Status", owner_id=1, status="active")
    cp = ChargePoint(
        id=1,
        code="CP-STATUS-TEST",
        station_id=1,
        status="online",
    )
    connector = Connector(
        id=1,
        charge_point_id=1,
        connector_id=1,
        status="unavailable",
        ocpp_status=None,
    )
    db.add_all([station, cp, connector])
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def _send_status(db, payload: dict, cp_code: str = "CP-STATUS-TEST", msg_id: str = "msg-1"):
    raw = pack_call(msg_id, "StatusNotification", payload)
    resp = handle_ocpp_message(db, cp_code, raw)
    if not resp:
        return None
    msg_type, resp_id, _, result, _, _ = parse_message(resp)
    return result


def test_status_notification_valid_connector(db_session):
    """Gửi Charging cho connectorId 1 -> cập nhật bận, raw = Charging."""
    result = _send_status(db_session, {"connectorId": 1, "errorCode": "NoError", "status": "Charging"})
    assert result == {}  # Phải trả về payload rỗng theo chuẩn OCPP 1.6

    db_session.expire_all()
    conn = db_session.query(Connector).filter_by(connector_id=1).one()
    assert conn.status == InternalStatus.BUSY.value
    assert conn.ocpp_status == "Charging"


def test_status_notification_strange_status(db_session):
    """Trạng thái lạ (ví dụ "Foo") -> cập nhật status = lỗi, raw = "Foo"."""
    _send_status(db_session, {"connectorId": 1, "errorCode": "NoError", "status": "Foo"})
    
    db_session.expire_all()
    conn = db_session.query(Connector).filter_by(connector_id=1).one()
    assert conn.status == InternalStatus.FAULTED.value
    assert conn.ocpp_status == "Foo"


def test_status_notification_connector_zero(db_session):
    """connectorId = 0: bảng connectors không bị đổi (không cập nhật cho conector 1)."""
    _send_status(db_session, {"connectorId": 0, "errorCode": "NoError", "status": "Faulted"})
    
    db_session.expire_all()
    # Connector 1 vẫn phải giữ nguyên trạng thái ban đầu là "unavailable" và None
    conn = db_session.query(Connector).filter_by(connector_id=1).one()
    assert conn.status == "unavailable"
    assert conn.ocpp_status is None


def test_status_notification_unknown_connector(db_session):
    """connectorId không tồn tại: không tạo bản ghi mới, không lỗi."""
    count_before = db_session.query(Connector).count()
    result = _send_status(db_session, {"connectorId": 99, "errorCode": "NoError", "status": "Available"})
    assert result == {}  # Không lỗi, trả về rỗng

    count_after = db_session.query(Connector).count()
    assert count_before == count_after  # Không tạo thêm
