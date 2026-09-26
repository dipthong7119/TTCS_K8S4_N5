from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
from app.models.charge_point import ChargePoint, Connector
from app.models.connector_error import ConnectorError
from app.services.ocpp_parser import pack_call_result, pack_call_error

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = {
    "BootNotification",
    "Heartbeat",
    "StatusNotification",
    "Authorize",
    "StartTransaction",
    "MeterValues",
    "StopTransaction",
    "Reset"
}

STATUS_MAPPING = {
    "Available": "rảnh",
    "Preparing": "bận",
    "Charging": "bận",
    "SuspendedEV": "bận",
    "SuspendedEVSE": "bận",
    "Finishing": "bận",
    "Reserved": "đặt chỗ",
    "Unavailable": "lỗi",
    "Faulted": "lỗi"
}

def handle_ocpp_message(db: Session, charge_point_code: str, raw_msg: str) -> str:
    from app.services.ocpp_parser import parse_message
    
    try:
        msg_type, msg_id, action, payload_or_err, err_desc, err_details = parse_message(raw_msg)
    except ValueError as e:
        err_msg = str(e)
        if "JSON format" in err_msg or "must be a JSON array" in err_msg or "not a valid string" in err_msg:
            return pack_call_error("", "FormationViolation", err_msg)
        return pack_call_error("", "ProtocolError", err_msg)

    if msg_type == 3:
        # T-34: Khớp CALLRESULT
        # Ở hệ thống thực tế ta có thể lấy request_id để resolve Future chờ
        logger.info(f"Nhận CALLRESULT từ {charge_point_code} cho msg_id {msg_id}: {payload_or_err}")
        return ""
    elif msg_type == 4:
        logger.error(f"Nhận CALLERROR từ {charge_point_code} cho msg_id {msg_id}: {payload_or_err} - {err_desc}")
        return ""

    if msg_type != 2:
        return pack_call_error(msg_id, "NotSupported", f"Not supporting message type {msg_type}")

    if action not in SUPPORTED_ACTIONS:
        return pack_call_error(msg_id, "NotImplemented", f"Action {action} is not implemented")

    # T-30: Check idempotency
    from app.models.ocpp_message import OcppMessage
    import json

    existing_msg = db.query(OcppMessage).filter(OcppMessage.msg_id == msg_id).first()
    if existing_msg:
        # Nếu đã xử lý, trả về y hệt kết quả cũ
        return existing_msg.response_payload

    cp = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if cp:
        cp.last_seen_at = datetime.now(timezone.utc)
        db.commit()

    response_str = None
    if action == "BootNotification":
        response_str = handle_boot_notification(db, charge_point_code, msg_id, payload_or_err)
    elif action == "Heartbeat":
        response_str = handle_heartbeat(db, charge_point_code, msg_id, payload_or_err)
    elif action == "StatusNotification":
        response_str = handle_status_notification(db, charge_point_code, msg_id, payload_or_err)
    elif action == "Authorize":
        response_str = handle_authorize(db, charge_point_code, msg_id, payload_or_err)
    else:
        response_str = pack_call_error(msg_id, "NotImplemented", f"Action {action} is planned but not coded yet")

    # Lưu lại để chống trùng
    if response_str:
        try:
            msg_record = OcppMessage(
                msg_id=msg_id,
                charge_point_code=charge_point_code,
                action=action,
                response_payload=response_str
            )
            db.add(msg_record)
            db.commit()
        except Exception as e:
            logger.error(f"Lỗi lưu ocpp_message: {e}")
            db.rollback()

    return response_str


def handle_boot_notification(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    cp = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if not cp:
        return pack_call_error(msg_id, "SecurityError", "Charge point not found")
        
    cp.vendor = payload.get("chargePointVendor", "")
    cp.model = payload.get("chargePointModel", "")
    cp.firmware_version = payload.get("firmwareVersion", "")
    
    station = cp.station
    if station and getattr(station, 'status', 'active') == 'inactive':
        status_response = "Rejected"
    else:
        status_response = "Accepted"
        cp.status = "online"
        
    db.commit()
    
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return pack_call_result(msg_id, {
        "currentTime": current_time,
        "interval": 300,
        "status": status_response
    })

def handle_heartbeat(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return pack_call_result(msg_id, {
        "currentTime": current_time
    })

def handle_status_notification(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    """T-20, T-21, T-22: Xử lý StatusNotification"""
    connector_id = payload.get("connectorId")
    status_raw = payload.get("status")
    error_code = payload.get("errorCode", "NoError")
    info = payload.get("info")
    vendor_error_code = payload.get("vendorErrorCode")
    # OCPP 1.6: timestamp
    ts_str = payload.get("timestamp")
    
    ts = None
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            pass

    cp = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if not cp:
        return pack_call_error(msg_id, "SecurityError", "Charge point not found")

    if connector_id == 0:
        # T-10 AC: Trạng thái của cả trụ (thay vì một đầu nối)
        # Chỉ cập nhật error nếu có
        cp.status = "online" if status_raw == "Available" else cp.status
        db.commit()
        return pack_call_result(msg_id, {})
    
    # T-22: Bỏ qua đầu nối chưa khai báo kèm cảnh báo
    connector = db.query(Connector).filter(
        Connector.charge_point_id == cp.id,
        Connector.connector_id == connector_id
    ).first()
    
    if not connector:
        logger.warning(f"Đầu nối chưa khai báo: trụ {charge_point_code}, cổng {connector_id}")
        return pack_call_result(msg_id, {})
        
    # T-20: Cập nhật trạng thái đầu nối
    mapped_status = STATUS_MAPPING.get(status_raw)
    if mapped_status:
        connector.status = mapped_status
    else:
        # T-20: Trạng thái lạ chưa biết lưu nguyên văn
        connector.status = status_raw
        
    connector.error_code = error_code

    # T-21: Lưu lỗi vào bảng connector_errors nếu có lỗi
    if error_code != "NoError" or status_raw in ["Faulted", "Unavailable"]:
        err = ConnectorError(
            connector_id=connector.id,
            error_code=error_code,
            vendor_error_code=vendor_error_code,
            info=info,
            timestamp=ts or datetime.now(timezone.utc)
        )
        db.add(err)

    db.commit()

    # Kích hoạt sự kiện SSE (T-25)
    from app.routers.monitoring import notify_status_change
    db.refresh(cp)

    # Chuẩn bị dữ liệu charge_points như cấu trúc trả về ở /api/monitoring/tree
    cp_data = []
    station = cp.station
    if station:
        for p in station.charge_points:
            conn_list = []
            for cn in p.connectors:
                conn_list.append({
                    "id": cn.id,
                    "connector_id": cn.connector_id,
                    "status": cn.status,
                    "error_code": cn.error_code,
                    "updated_at": cn.updated_at.isoformat()
                })
            cp_data.append({
                "id": p.id,
                "code": p.code,
                "status": p.status,
                "vendor": p.vendor,
                "model": p.model,
                "firmware_version": p.firmware_version,
                "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
                "connectors": conn_list
            })
        notify_status_change(station.id, cp_data)

    return pack_call_result(msg_id, {})

def handle_authorize(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    from app.models.id_tag import IdTag
    id_tag_str = payload.get("idTag")
    if not id_tag_str:
        return pack_call_error(msg_id, "FormationViolation", "Missing idTag")

    status = "Invalid"
    tag = db.query(IdTag).filter(IdTag.id_tag == id_tag_str).first()
    if tag:
        # compare with naive UTC or aware UTC based on DB driver
        now = datetime.now(timezone.utc)
        if tag.is_blocked:
            status = "Blocked"
        elif tag.expiry_date and tag.expiry_date.replace(tzinfo=timezone.utc) < now:
            status = "Expired"
        else:
            status = "Accepted"

    # expiryDate is optional in OCPP if null
    id_tag_info = {"status": status}
    if tag and tag.expiry_date:
        id_tag_info["expiryDate"] = tag.expiry_date.isoformat() + "Z"

    return pack_call_result(msg_id, {"idTagInfo": id_tag_info})

