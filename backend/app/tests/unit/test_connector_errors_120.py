"""Test logic ghi lỗi vào connector_errors từ StatusNotification (SCRUM-120)."""

import pytest
from datetime import datetime, UTC
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.models.connector_error import ConnectorError
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


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

    station = Station(id=1, name="Station 1", owner_id=1, status="active")
    cp = ChargePoint(id=1, code="CP-120", station_id=1, status="online")
    connector = Connector(id=1, charge_point_id=1, connector_id=1, status="unavailable")
    
    db.add_all([station, cp, connector])
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def _send_status(db, payload: dict, cp_code: str = "CP-120", msg_id: str = "msg-120"):
    raw = pack_call(msg_id, "StatusNotification", payload)
    resp = handle_ocpp_message(db, cp_code, raw)
    if not resp:
        return None
    msg_type, resp_id, _, result, _, _ = parse_message(resp)
    return result


def test_status_notification_records_error(db_session):
    """Gửi Faulted với errorCode GroundFailure và vendorErrorCode E42 -> ghi 1 dòng."""
    _send_status(db_session, {
        "connectorId": 1,
        "status": "Faulted",
        "errorCode": "GroundFailure",
        "vendorErrorCode": "E42"
    })

    errors = db_session.query(ConnectorError).all()
    assert len(errors) == 1
    assert errors[0].connector_id == 1
    assert errors[0].error_code == "GroundFailure"
    assert errors[0].vendor_error_code == "E42"


def test_status_notification_no_error_preserves_old(db_session):
    """Gửi lỗi rồi gửi Available (NoError) -> không xoá dòng cũ, không thêm dòng mới."""
    _send_status(db_session, {"connectorId": 1, "status": "Faulted", "errorCode": "GroundFailure"})
    assert db_session.query(ConnectorError).count() == 1

    # Gửi NoError
    _send_status(db_session, {"connectorId": 1, "status": "Available", "errorCode": "NoError"})
    assert db_session.query(ConnectorError).count() == 1  # Vẫn là 1


def test_status_notification_no_error_initially(db_session):
    """errorCode = NoError ngay từ đầu -> không có lỗi nào."""
    _send_status(db_session, {"connectorId": 1, "status": "Available", "errorCode": "NoError"})
    assert db_session.query(ConnectorError).count() == 0


def test_status_notification_missing_vendor_error(db_session):
    """Thiếu vendorErrorCode -> ghi với NULL."""
    _send_status(db_session, {"connectorId": 1, "status": "Faulted", "errorCode": "HighTemperature"})
    error = db_session.query(ConnectorError).first()
    assert error.vendor_error_code is None


def test_status_notification_custom_timestamp(db_session):
    """Có timestamp hợp lệ -> lấy theo timestamp đó, chuẩn hoá UTC."""
    custom_ts = "2026-10-02T15:00:00Z"
    _send_status(db_session, {
        "connectorId": 1,
        "status": "Faulted",
        "errorCode": "GroundFailure",
        "timestamp": custom_ts
    })
    
    error = db_session.query(ConnectorError).first()
    assert error.occurred_at == datetime(2026, 10, 2, 15, 0, 0)


def test_status_notification_invalid_timestamp_fallback(db_session):
    """Timestamp sai định dạng -> dùng giờ máy chủ."""
    _send_status(db_session, {
        "connectorId": 1,
        "status": "Faulted",
        "errorCode": "GroundFailure",
        "timestamp": "invalid-time"
    })
    
    error = db_session.query(ConnectorError).first()
    assert error.occurred_at is not None  # Đã fallback thành công


def test_status_notification_two_errors(db_session):
    """Hai lỗi liên tiếp -> ghi hai dòng."""
    _send_status(db_session, {"connectorId": 1, "status": "Faulted", "errorCode": "Err1"})
    _send_status(db_session, {"connectorId": 1, "status": "Faulted", "errorCode": "Err2"})
    
    errors = db_session.query(ConnectorError).order_by(ConnectorError.occurred_at.asc()).all()
    assert len(errors) == 2
    assert errors[0].error_code == "Err1"
    assert errors[1].error_code == "Err2"


def test_status_notification_zero_or_unknown_connector(db_session):
    """connectorId = 0 hoặc lạ -> không ghi gì, không lỗi."""
    # ID = 0
    _send_status(db_session, {"connectorId": 0, "status": "Faulted", "errorCode": "Err0"})
    assert db_session.query(ConnectorError).count() == 0
    
    # ID = 99
    _send_status(db_session, {"connectorId": 99, "status": "Faulted", "errorCode": "Err99"})
    assert db_session.query(ConnectorError).count() == 0
