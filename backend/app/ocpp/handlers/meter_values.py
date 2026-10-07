"""Handler cho sự kiện MeterValues."""

import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.models.orphan_message import OrphanMessage
from app.services.ocpp_handlers import _parse_timestamp
from app.services.ocpp_parser import pack_call_error, pack_call_result

logger = logging.getLogger(__name__)

# Danh sách các đại lượng được lưu
KNOWN_MEASURANDS = {
    "Energy.Active.Import.Register",
    "Power.Active.Import",
    "Current.Import",
}


def parse_meter_values(payload: dict) -> list[dict]:
    """Hàm thuần phân tích payload MeterValues thành danh sách dict để lưu."""
    readings = payload.get("meterValue")
    if not isinstance(readings, list):
        raise TypeError("meterValue must be an array")

    # Fallback cho trường hợp không có timestamp trong sampledValue
    # Tuy nhiên spec OCPP 1.6 yêu cầu timestamp nằm ở meterValue, không ở sampledValue.

    normalized = []
    for reading in readings:
        if not isinstance(reading, dict):
            continue

        timestamp_str = reading.get("timestamp")
        if not timestamp_str:
            raise ValueError("Missing timestamp in meterValue")

        measured_at = _parse_timestamp(timestamp_str)
        if measured_at is None:
            raise ValueError("Invalid timestamp format")

        samples = reading.get("sampledValue")
        if not isinstance(samples, list):
            raise TypeError("sampledValue must be an array")

        for sample in samples:
            if not isinstance(sample, dict):
                continue

            measurand = sample.get("measurand") or "Energy.Active.Import.Register"
            if measurand not in KNOWN_MEASURANDS:
                logger.debug("Skipping unsupported measurand: %s", measurand)
                continue

            raw_value = sample.get("value")
            if raw_value is None:
                logger.warning("Missing value in sampledValue for %s", measurand)
                continue

            try:
                # Bỏ qua nếu là chuỗi trống hoặc không thể chuyển sang Decimal
                value = Decimal(str(raw_value))
                if not value.is_finite():
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                logger.warning("Invalid number format for value: %s", raw_value)
                continue

            raw_unit = sample.get("unit")
            unit = raw_unit if isinstance(raw_unit, str) and raw_unit else None

            normalized.append(
                {
                    "measured_at": measured_at,
                    "measurand": measurand,
                    "value": value,
                    "unit": unit,
                }
            )

    return normalized


def filter_new_samples(session_id: int, samples: list[dict]) -> list[dict]:
    """
    Điểm chèn rõ ràng cho bước so mốc thời gian (T-42).
    Hiện tại trả về đúng danh sách đầu vào.
    """
    return samples


def handle_meter_values(db: Session, point: ChargePoint, msg_id: str, payload: dict) -> str:
    """Xử lý sự kiện MeterValues."""
    connector_number = payload.get("connectorId")
    transaction_id = payload.get("transactionId")

    if type(connector_number) is not int or connector_number < 0:
        return pack_call_error(msg_id, "PropertyConstraintViolation", "connectorId must be a non-negative integer")
    if transaction_id is not None and type(transaction_id) is not int:
        return pack_call_error(msg_id, "PropertyConstraintViolation", "transactionId must be an integer")

    try:
        raw_samples = parse_meter_values(payload)
    except (TypeError, ValueError) as e:
        return pack_call_error(msg_id, "FormationViolation", str(e))

    # Khớp phiên sạc
    query = db.query(ChargingSession).filter(ChargingSession.charge_point_id == point.id)
    if transaction_id is not None:
        query = query.filter(ChargingSession.id == transaction_id)
    else:
        query = query.filter(
            ChargingSession.connector_number == connector_number,
            ChargingSession.ended_at.is_(None)
        )

    session = query.order_by(ChargingSession.id.desc()).first()

    # Không có phiên: trả conf trước (ở framework trả luôn sau hàm này),
    # nhưng yêu cầu "ghi orphan_messages, không ghi meter_values, ghi cảnh báo ngắn".
    if session is None or (transaction_id is not None and session.ended_at is not None):
        reason = "no_active_session" if session is None else "session_ended"
        db.add(OrphanMessage(
            charge_point_code=point.code,
            action="MeterValues",
            transaction_id=transaction_id,
            connector_number=connector_number,
            reason=reason,
            payload=payload,
        ))
        logger.warning(
            "Orphan MeterValues: cp=%s conn=%s tx=%s reason=%s",
            point.code, connector_number, transaction_id, reason
        )
        return pack_call_result(msg_id, {})

    filtered_samples = filter_new_samples(session.id, raw_samples)

    if filtered_samples:
        db.add_all([
            MeterValue(
                session_id=session.id,
                measured_at=sample["measured_at"],
                measurand=sample["measurand"],
                value=sample["value"],
                unit=sample["unit"],
            )
            for sample in filtered_samples
        ])
        logger.debug("Saved %d meter values for cp=%s conn=%s", len(filtered_samples), point.code, connector_number)

    return pack_call_result(msg_id, {})
