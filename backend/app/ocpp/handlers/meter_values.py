"""Handler cho sự kiện MeterValues."""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, TypedDict

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.models.orphan_message import OrphanMessage
from app.services.meter_values import get_latest_meter_value
from app.services.ocpp_handlers import _parse_timestamp
from app.services.ocpp_parser import pack_call_error, pack_call_result

logger = logging.getLogger(__name__)


class MeterSample(TypedDict):
    measured_at: datetime
    measurand: str
    value: Decimal
    unit: str | None


class Decision(Enum):
    """Kết quả so sánh một số đo với số đo gần nhất."""

    STORE = "store"
    STORE_AND_FLAG = "store_and_flag"
    SKIP_WARN = "skip_warn"
    SKIP_SILENT = "skip_silent"

# Danh sách các đại lượng được lưu
KNOWN_MEASURANDS = {
    "Energy.Active.Import.Register",
    "Power.Active.Import",
    "Current.Import",
}


def parse_meter_values(payload: dict[str, Any]) -> list[MeterSample]:
    """Hàm thuần phân tích payload MeterValues thành danh sách dict để lưu."""
    readings = payload.get("meterValue")
    if not isinstance(readings, list):
        raise TypeError("meterValue must be an array")

    # Fallback cho trường hợp không có timestamp trong sampledValue
    # Tuy nhiên spec OCPP 1.6 yêu cầu timestamp nằm ở meterValue, không ở sampledValue.

    normalized: list[MeterSample] = []
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


def _unit_in_wh(value: Decimal, unit: str | None) -> Decimal | None:
    """Đổi Wh/kWh về Wh; thiếu đơn vị được hiểu là Wh."""
    normalized = unit or "Wh"
    if normalized == "Wh":
        return value
    if normalized == "kWh":
        return value * Decimal(1000)
    return None


def _comparable_values(
    new: MeterSample, latest: MeterSample | MeterValue
) -> tuple[Decimal, Decimal] | None:
    new_unit = new.get("unit") or "Wh"
    latest_unit = latest.get("unit") or "Wh" if isinstance(latest, dict) else latest.unit or "Wh"
    new_value = Decimal(str(new["value"]))
    latest_value = Decimal(str(latest["value"] if isinstance(latest, dict) else latest.value))
    if new_unit == latest_unit:
        return new_value, latest_value
    converted_new = _unit_in_wh(new_value, new_unit)
    converted_latest = _unit_in_wh(latest_value, latest_unit)
    if converted_new is None or converted_latest is None:
        return None
    return converted_new, converted_latest


def decide_sample(new: MeterSample, latest: MeterSample | MeterValue | None) -> Decision:
    """Quyết định thuần theo mốc trong tin nhắn và số đo đã có."""
    if latest is None:
        return Decision.STORE
    new_at: datetime = new["measured_at"]
    latest_at: datetime = latest["measured_at"] if isinstance(latest, dict) else latest.measured_at
    if new_at < latest_at:
        return Decision.SKIP_WARN
    comparable = _comparable_values(new, latest)
    if new_at == latest_at:
        if comparable is not None and comparable[0] == comparable[1]:
            return Decision.SKIP_SILENT
        return Decision.SKIP_WARN
    if comparable is None:
        return Decision.STORE
    if (
        new["measurand"] == "Energy.Active.Import.Register"
        and comparable[0] < comparable[1]
    ):
        return Decision.STORE_AND_FLAG
    return Decision.STORE


def begin_meter_values_transaction(db: Session) -> None:
    """Lấy khóa ghi SQLite trước các truy vấn của MeterValues."""
    if db.bind is None or db.bind.dialect.name != "sqlite":
        return
    connection = db.connection()
    raw_connection = connection.connection.driver_connection
    assert raw_connection is not None
    if not raw_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def filter_new_samples(
    db: Session,
    session_id: int,
    samples: list[MeterSample],
    charge_point_code: str,
) -> list[MeterSample]:
    """Lọc theo từng đại lượng, gồm cả số đo đã nhận trong cùng tin nhắn."""
    latest_by_measurand: dict[str, MeterSample | MeterValue | None] = {}
    accepted: list[MeterSample] = []
    should_flag = False
    ordered_samples = sorted(samples, key=lambda item: item["measured_at"])
    existing_by_key: dict[tuple[str, datetime], MeterValue] = {}
    if ordered_samples:
        measurands = {sample["measurand"] for sample in ordered_samples}
        timestamps = {sample["measured_at"] for sample in ordered_samples}
        existing_rows = db.execute(
            select(MeterValue).where(
                MeterValue.session_id == session_id,
                MeterValue.measurand.in_(measurands),
                MeterValue.measured_at.in_(timestamps),
            )
        ).scalars()
        existing_by_key = {
            (row.measurand, row.measured_at): row for row in existing_rows
        }

    for sample in ordered_samples:
        measurand = sample["measurand"]
        if measurand not in latest_by_measurand:
            latest_by_measurand[measurand] = get_latest_meter_value(db, session_id, measurand)
        latest = latest_by_measurand[measurand]
        if latest is not None:
            comparable_values = _comparable_values(sample, latest)
            latest_unit = (latest.get("unit") if isinstance(latest, dict) else latest.unit) or "Wh"
            sample_unit = sample.get("unit") or "Wh"
            latest_at = latest["measured_at"] if isinstance(latest, dict) else latest.measured_at
            if (
                sample["measured_at"] > latest_at
                and comparable_values is None
                and sample_unit != latest_unit
            ):
                logger.warning(
                    "Meter value units not comparable: cp=%s session=%s measurand=%s",
                    charge_point_code, session_id, measurand,
                )
        decision = decide_sample(sample, latest)
        if decision is Decision.SKIP_WARN:
            assert latest is not None
            persisted = existing_by_key.get((measurand, sample["measured_at"]))
            if persisted is not None:
                prior_values = _comparable_values(sample, persisted)
                if prior_values is not None and prior_values[0] == prior_values[1]:
                    logger.debug(
                        "Duplicate meter value: cp=%s session=%s measurand=%s",
                        charge_point_code, session_id, measurand,
                    )
                    continue
            old_at = latest["measured_at"] if isinstance(latest, dict) else latest.measured_at
            logger.warning(
                "Meter value rejected: cp=%s session=%s measurand=%s old_at=%s new_at=%s",
                charge_point_code, session_id, measurand, old_at.isoformat(),
                sample["measured_at"].isoformat(),
            )
        elif decision is Decision.SKIP_SILENT:
            logger.debug("Duplicate meter value: cp=%s session=%s measurand=%s", charge_point_code, session_id, measurand)
        else:
            accepted.append(sample)
            latest_by_measurand[measurand] = sample
            should_flag = should_flag or decision is Decision.STORE_AND_FLAG

    if should_flag:
        db.execute(
            update(ChargingSession)
            .where(ChargingSession.id == session_id)
            .values(
                needs_review=True,
                review_reason=text("coalesce(review_reason, 'meter_value_decreased')"),
            )
        )
    return accepted


def store_meter_samples(
    db: Session, session_id: int, samples: list[MeterSample], charge_point_code: str
) -> list[MeterSample]:
    """Dùng chung quy tắc thời gian/chống trùng cho MeterValues và StopTransaction."""
    filtered = filter_new_samples(db, session_id, samples, charge_point_code)
    db.add_all([
        MeterValue(
            session_id=session_id,
            measured_at=sample["measured_at"],
            measurand=sample["measurand"],
            value=sample["value"],
            unit=sample["unit"],
        )
        for sample in filtered
    ])
    return filtered


def handle_meter_values(
    db: Session, point: ChargePoint, msg_id: str, payload: dict[str, Any]
) -> str:
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

    begin_meter_values_transaction(db)
    # Khớp phiên sạc
    query = db.query(ChargingSession).filter(ChargingSession.charge_point_id == point.id)
    if transaction_id is not None:
        query = query.filter(ChargingSession.id == transaction_id)
    else:
        query = query.filter(
            ChargingSession.connector_number == connector_number,
            ChargingSession.ended_at.is_(None)
        )

    session = query.order_by(ChargingSession.id.desc()).with_for_update().first()

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

    filtered_samples = store_meter_samples(db, session.id, raw_samples, point.code)

    if filtered_samples:
        logger.debug("Saved %d meter values for cp=%s conn=%s", len(filtered_samples), point.code, connector_number)

    return pack_call_result(msg_id, {})
