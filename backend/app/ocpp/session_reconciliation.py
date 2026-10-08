"""Đối chiếu phiên sạc đang mở khi trụ kết nối trở lại."""

import logging
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.services.ocpp_status import is_charge_point_stale

logger = logging.getLogger(__name__)

# Ba trạng thái chưa có StopTransaction và còn cần theo dõi khi trụ nối lại.
OPEN_SESSION_STATUSES: tuple[str, ...] = ("active", "needs_review", "anomaly")


class ReconciliationDecision(Enum):
    KEEP = "KEEP"
    FLAG = "FLAG"
    NONE = "NONE"


@dataclass
class ReconciliationContext:
    """Trạng thái đối chiếu chỉ thuộc một kết nối WebSocket."""

    waiting: dict[int, int] = field(default_factory=dict)
    decided: set[int] = field(default_factory=set)
    missing_session_logged: set[int] = field(default_factory=set)
    initialized: bool = False
    offline_reconciled: bool = False


def decide_reconciliation(status: str) -> ReconciliationDecision:
    """Quyết định thuần theo trạng thái đầu nối OCPP."""
    if status in {"Charging", "SuspendedEV", "SuspendedEVSE"}:
        return ReconciliationDecision.KEEP
    if status == "Available":
        return ReconciliationDecision.FLAG
    return ReconciliationDecision.NONE


def _open_sessions_statement(charge_point_id: int) -> Select[tuple[int, int]]:
    return (
        select(Connector.connector_id, ChargingSession.id)
        .join(
            ChargingSession,
            (ChargingSession.charge_point_id == Connector.charge_point_id)
            & (ChargingSession.connector_number == Connector.connector_id),
        )
        .where(
            Connector.charge_point_id == charge_point_id,
            ChargingSession.ended_at.is_(None),
            ChargingSession.status.in_(OPEN_SESSION_STATUSES),
        )
    )


def begin_reconciliation(
    db: Session,
    charge_point: ChargePoint,
    connection_ctx: ReconciliationContext,
) -> dict[int, int]:
    """Dựng lại map đầu nối → transactionId bằng đúng một truy vấn."""
    connection_ctx.initialized = False
    connection_ctx.waiting.clear()
    connection_ctx.decided.clear()
    connection_ctx.missing_session_logged.clear()
    rows = db.execute(_open_sessions_statement(charge_point.id)).mappings().all()
    pending = {int(row["connector_id"]): int(row["id"]) for row in rows}
    connection_ctx.waiting = pending
    connection_ctx.initialized = True
    return dict(pending)


def reconcile_if_offline(
    db: Session,
    charge_point_code: str,
    connection_ctx: ReconciliationContext,
) -> bool:
    """Dựng lại map khi trụ bị đánh dấu offline trên kết nối đang sống."""
    point = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if point is None:
        return False
    is_offline = point.status == "offline" or is_charge_point_stale(point.last_seen_at)
    if not is_offline and connection_ctx.initialized:
        connection_ctx.offline_reconciled = False
        return False
    if not connection_ctx.offline_reconciled:
        with db.begin_nested():
            begin_reconciliation(db, point, connection_ctx)
        connection_ctx.offline_reconciled = is_offline
    return is_offline


def reconcile_status_notification(
    db: Session,
    charge_point_code: str,
    connector_id: int,
    status: str,
    connection_ctx: ReconciliationContext,
) -> ReconciliationDecision:
    """Xử lý trạng thái đầu nối đầu tiên trong phiên kết nối hiện tại."""
    transaction_id = connection_ctx.waiting.get(connector_id)
    if transaction_id is None:
        if (
            status == "Charging"
            and connection_ctx.initialized
            and connector_id not in connection_ctx.decided
            and connector_id not in connection_ctx.missing_session_logged
        ):
            logger.info(
                "Charging without open session: cp=%s connector=%s",
                charge_point_code,
                connector_id,
            )
            connection_ctx.missing_session_logged.add(connector_id)
        return ReconciliationDecision.NONE

    decision = decide_reconciliation(status)
    if decision is ReconciliationDecision.NONE:
        logger.debug(
            "Session reconciliation: cp=%s connector=%s transaction=%s decision=%s",
            charge_point_code,
            connector_id,
            transaction_id,
            decision.value,
        )
        return decision

    if decision is ReconciliationDecision.FLAG:
        # Savepoint để lỗi cập nhật phiên không làm hỏng cập nhật connector.
        with db.begin_nested():
            db.execute(
                update(ChargingSession)
                .where(
                    ChargingSession.id == transaction_id,
                    ChargingSession.status == "active",
                    ChargingSession.ended_at.is_(None),
                )
                .values(
                    status="needs_review",
                    review_reason=func.coalesce(
                        ChargingSession.review_reason,
                        "connector_available_after_reconnect",
                    ),
                )
            )

    connection_ctx.waiting.pop(connector_id, None)
    connection_ctx.decided.add(connector_id)
    log = logger.warning if decision is ReconciliationDecision.FLAG else logger.debug
    log(
        "Session reconciliation: cp=%s connector=%s transaction=%s decision=%s",
        charge_point_code,
        connector_id,
        transaction_id,
        decision.value,
    )
    return decision
