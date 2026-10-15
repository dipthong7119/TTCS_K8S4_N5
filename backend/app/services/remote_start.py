"""Nghiệp vụ RemoteStartTransaction của tài xế (S-24 / T-51)."""

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from math import ceil
from typing import Any, cast

from sqlalchemy import and_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.id_tag import IdTag
from app.models.remote_start_request import RemoteStartRequest, RemoteStartStatus
from app.models.station import Station
from app.models.user import User
from app.ocpp.session_statuses import OPEN_SESSION_STATUSES
from app.services.audit import append_audit
from app.services.connection_manager import manager
from app.services.ocpp_parser import OCPPError
from app.services.ocpp_status import is_charge_point_stale
from app.services.wallet import has_minimum_balance, minimum_wallet_balance_vnd

logger = logging.getLogger(__name__)


class ConnectorDecision(str, Enum):
    """Kết quả kiểm tra thuần trước khi gửi lệnh."""

    ALLOW = "allow"
    BUSY = "busy"
    RESERVED = "reserved"
    FAULTED = "faulted"
    UNAVAILABLE = "unavailable"


class RemoteStartFailure(Exception):
    """Lỗi nghiệp vụ đã có mã HTTP và mã máy đọc được."""

    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        *,
        minimum_required_vnd: int | None = None,
        top_up_url: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.minimum_required_vnd = minimum_required_vnd
        self.top_up_url = top_up_url


def decide_connector_start(
    raw_status: str | None,
    has_open_session: bool,
    allowed_statuses: tuple[str, ...] | None = None,
) -> ConnectorDecision:
    """Quyết định thuần đầu nối có đủ điều kiện bắt đầu hay không."""
    if has_open_session:
        return ConnectorDecision.BUSY
    if raw_status == "Reserved":
        return ConnectorDecision.RESERVED
    if raw_status in {"Faulted", "Unavailable"}:
        return ConnectorDecision.FAULTED
    allowed = (
        settings.REMOTE_START_ALLOWED_STATUSES
        if allowed_statuses is None
        else allowed_statuses
    )
    if raw_status not in allowed:
        return ConnectorDecision.UNAVAILABLE
    return ConnectorDecision.ALLOW


def check_start_policy(db: Session, driver_user_id: int, connector_id: int) -> None:
    """Chặn RemoteStart khi số dư ví thấp hơn ngưỡng toàn hệ thống (SCRUM-72)."""
    minimum_required_vnd = minimum_wallet_balance_vnd(db)
    if has_minimum_balance(db, driver_user_id, minimum_required_vnd):
        return
    db.rollback()
    logger.info(
        "Remote start blocked: connector_id=%s reason=wallet_below_minimum",
        connector_id,
    )
    raise RemoteStartFailure(
        409,
        "wallet_below_minimum",
        f"Số dư ví cần tối thiểu {minimum_required_vnd:,} đồng. Hãy nạp thêm tiền để bắt đầu phiên sạc.",
        minimum_required_vnd=minimum_required_vnd,
        top_up_url="/wallet",
    )


def utc_now_naive() -> datetime:
    """Dự án lưu thời gian UTC dưới dạng datetime không timezone."""
    return datetime.now(UTC).replace(tzinfo=None)


def _lock_virtual_tag_write(db: Session, user_id: int) -> None:
    """Khóa theo tài xế để hai yêu cầu không cùng sinh thẻ ảo."""
    if db.get_bind().dialect.name == "sqlite":
        connection = db.connection()
        raw_connection = connection.connection.driver_connection
        if raw_connection is not None and not raw_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        return
    db.execute(select(User.id).where(User.id == user_id).with_for_update()).first()


def ensure_virtual_id_tag(db: Session, user_id: int) -> IdTag:
    """Đảm bảo tài xế có đúng một thẻ ảo, an toàn khi gọi lặp."""
    _lock_virtual_tag_write(db, user_id)
    current = (
        db.query(IdTag)
        .filter(IdTag.user_id == user_id, IdTag.is_virtual.is_(True))
        .first()
    )
    if current is not None:
        return current

    for _ in range(5):
        candidate = IdTag(
            id_tag=f"V{secrets.token_urlsafe(12)}",
            user_id=user_id,
            is_virtual=True,
            is_blocked=False,
            expiry_date=None,
        )
        try:
            # Savepoint giúp lỗi trùng không làm hỏng transaction của user.
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            return candidate
        except IntegrityError:
            db.expire_all()
            current = (
                db.query(IdTag)
                .filter(IdTag.user_id == user_id, IdTag.is_virtual.is_(True))
                .first()
            )
            if current is not None:
                return current
    raise RuntimeError("Không tạo được thẻ ảo duy nhất")


def lock_remote_start_writes(db: Session, connector_id: int) -> None:
    """Khóa ngắn lúc tạo/đọc trạng thái yêu cầu, tránh hai lệnh cùng lọt qua."""
    db.rollback()
    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        connection = db.connection()
        raw_connection = connection.connection.driver_connection
        if raw_connection is not None and not raw_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        return
    db.execute(
        select(Connector.id)
        .where(Connector.id == connector_id)
        .with_for_update()
    ).first()


def expire_waiting_requests(db: Session, now: datetime) -> int:
    """Hết hạn dựa trên expires_at, không phụ thuộc job chạy nền."""
    result = db.execute(
        update(RemoteStartRequest)
        .where(
            RemoteStartRequest.status == RemoteStartStatus.WAITING_START,
            RemoteStartRequest.expires_at <= now,
        )
        .values(
            status=RemoteStartStatus.EXPIRED,
            resolved_at=now,
            detail="start_timeout",
        )
        .execution_options(synchronize_session="fetch")
    )
    return int(cast(CursorResult[Any], result).rowcount or 0)


def _active_request(db: Session, connector_id: int) -> RemoteStartRequest | None:
    return (
        db.query(RemoteStartRequest)
        .filter(
            RemoteStartRequest.connector_id == connector_id,
            RemoteStartRequest.status.in_(
                [RemoteStartStatus.SENDING, RemoteStartStatus.WAITING_START]
            ),
        )
        .order_by(RemoteStartRequest.created_at.desc(), RemoteStartRequest.id.desc())
        .first()
    )


def _joined_connector(
    db: Session, connector_id: int
) -> tuple[Connector, ChargePoint, Station, ChargingSession | None] | None:
    """Đọc đầu nối, trụ, trạm và phiên mở bằng một truy vấn join."""
    open_session = and_(
        ChargingSession.charge_point_id == ChargePoint.id,
        ChargingSession.connector_number == Connector.connector_id,
        ChargingSession.ended_at.is_(None),
        ChargingSession.status.in_(OPEN_SESSION_STATUSES),
    )
    row = (
        db.query(Connector, ChargePoint, Station, ChargingSession)
        .join(ChargePoint, Connector.charge_point_id == ChargePoint.id)
        .join(Station, ChargePoint.station_id == Station.id)
        .outerjoin(ChargingSession, open_session)
        .filter(Connector.id == connector_id)
        .first()
    )
    return row


def _preflight(
    db: Session, connector_id: int, driver_user_id: int, now: datetime
) -> tuple[Connector, ChargePoint, Station]:
    joined = _joined_connector(db, connector_id)
    if joined is None:
        db.rollback()
        logger.info("Remote start blocked: connector_id=%s reason=not_found", connector_id)
        raise RemoteStartFailure(404, "connector_not_found", "Không tìm thấy đầu nối.")
    connector, point, station, open_session = joined
    connector_pk = connector.id
    if station.status != "active":
        db.rollback()
        logger.info("Remote start blocked: connector_id=%s reason=station_suspended", connector_pk)
        raise RemoteStartFailure(409, "station_suspended", "Trạm đang tạm ngừng hoạt động.")
    if (
        point.code not in manager.active_connections
        or point.status != "online"
        or is_charge_point_stale(point.last_seen_at, now.replace(tzinfo=UTC))
    ):
        db.rollback()
        logger.info("Remote start blocked: connector_id=%s reason=charge_point_offline", connector_pk)
        raise RemoteStartFailure(409, "charge_point_offline", "Trụ sạc đang ngoại tuyến.")

    decision = decide_connector_start(connector.ocpp_status, open_session is not None)
    if decision != ConnectorDecision.ALLOW:
        db.rollback()
        logger.info("Remote start blocked: connector_id=%s reason=%s", connector_pk, decision.value)
        messages = {
            ConnectorDecision.BUSY: "Đầu nối đang có phiên sạc.",
            ConnectorDecision.RESERVED: "Đầu nối đang được đặt chỗ.",
            ConnectorDecision.FAULTED: "Đầu nối đang báo lỗi.",
            ConnectorDecision.UNAVAILABLE: "Đầu nối chưa sẵn sàng để bắt đầu.",
        }
        raise RemoteStartFailure(409, "connector_not_available", messages[decision])

    check_start_policy(db, driver_user_id, connector.id)
    return connector, point, station


def _message_for(status: RemoteStartStatus) -> str:
    return {
        RemoteStartStatus.SENDING: "Đang chờ trụ phản hồi lệnh.",
        RemoteStartStatus.WAITING_START: "Trụ đã nhận lệnh, đang chờ phiên bắt đầu.",
        RemoteStartStatus.STARTED: "Phiên sạc đã bắt đầu.",
        RemoteStartStatus.REJECTED: "Trụ từ chối. Hãy kiểm tra súng đã cắm chắc chưa rồi thử lại.",
        RemoteStartStatus.NO_REPLY: "Trụ không phản hồi, bạn có thể thử lại.",
        RemoteStartStatus.CHARGER_ERROR: "Trụ gặp lỗi khi xử lý lệnh, bạn có thể thử lại.",
        RemoteStartStatus.EXPIRED: "Phiên chưa bắt đầu được, bạn có thể thử lại.",
        RemoteStartStatus.SUPERSEDED: "Đầu nối đã bắt đầu phiên khác.",
    }[status]


def seconds_left(expires_at: datetime | None, now: datetime) -> int | None:
    if expires_at is None:
        return None
    return max(0, ceil((expires_at - now).total_seconds()))


def _audit_sent_command(
    db: Session,
    *,
    driver_user_id: int,
    connector_pk: int,
    outcome: str,
) -> None:
    """Một dòng audit không chứa mã thẻ, email, tên hay mã trụ."""
    append_audit(
        db,
        action="connector.remote_start.sent",
        object_type="connector",
        object_id=connector_pk,
        actor_id=driver_user_id,
        details={"command": "RemoteStartTransaction", "outcome": outcome},
    )


def _finish_call(
    db: Session,
    request_id: int,
    *,
    driver_user_id: int,
    connector_pk: int,
    status: RemoteStartStatus,
    now: datetime,
    accepted: bool = False,
    detail: str | None = None,
) -> RemoteStartRequest:
    accepted_at = now if accepted else None
    expires_at = now + timedelta(seconds=settings.REMOTE_START_WAIT) if accepted else None
    db.execute(
        update(RemoteStartRequest)
        .where(
            RemoteStartRequest.id == request_id,
            RemoteStartRequest.status == RemoteStartStatus.SENDING,
        )
        .values(
            status=status,
            accepted_at=accepted_at,
            expires_at=expires_at,
            resolved_at=None if accepted else now,
            detail=detail,
        )
        .execution_options(synchronize_session=False)
    )
    _audit_sent_command(
        db,
        driver_user_id=driver_user_id,
        connector_pk=connector_pk,
        outcome=detail or status.value,
    )
    db.commit()
    db.expire_all()
    return db.get(RemoteStartRequest, request_id)  # type: ignore[return-value]


async def submit_remote_start(
    db: Session, connector_id: int, driver_user_id: int
) -> tuple[RemoteStartRequest, bool]:
    """Tạo yêu cầu, commit trước khi chờ CALLRESULT và trả cờ đã gửi lệnh."""
    lock_remote_start_writes(db, connector_id)
    now = utc_now_naive()
    connector, point, _station = _preflight(db, connector_id, driver_user_id, now)
    connector_pk = connector.id
    ocpp_connector_number = connector.connector_id
    charge_point_code = point.code

    expire_waiting_requests(db, now)
    active = _active_request(db, connector_id)
    if active is not None:
        db.commit()
        if active.driver_user_id == driver_user_id:
            return active, False
        logger.info(
            "Remote start blocked: connector_id=%s reason=active_request",
            connector_pk,
        )
        raise RemoteStartFailure(
            409,
            "connector_not_available",
            "Đầu nối đang có yêu cầu bắt đầu khác.",
        )

    tag = ensure_virtual_id_tag(db, driver_user_id)
    request_row = RemoteStartRequest(
        driver_user_id=driver_user_id,
        connector_id=connector_pk,
        id_tag_id=tag.id,
        status=RemoteStartStatus.SENDING,
        created_at=now,
    )
    db.add(request_row)
    try:
        db.flush()
        request_id = request_row.id
        tag_value = tag.id_tag
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        active = _active_request(db, connector_id)
        if active is not None and active.driver_user_id == driver_user_id:
            return active, False
        raise RemoteStartFailure(
            409,
            "connector_not_available",
            "Đầu nối đang có yêu cầu bắt đầu khác.",
        ) from exc

    payload = {"idTag": tag_value, "connectorId": ocpp_connector_number}
    try:
        result = await manager.send_call(
            charge_point_code,
            "RemoteStartTransaction",
            payload,
            timeout=settings.REMOTE_START_CALL_TIMEOUT,
        )
    except asyncio.CancelledError:
        _finish_call(
            db,
            request_id,
            driver_user_id=driver_user_id,
            connector_pk=connector_pk,
            status=RemoteStartStatus.NO_REPLY,
            now=utc_now_naive(),
            detail="no_reply",
        )
        raise
    except asyncio.TimeoutError as exc:
        stored = _finish_call(
            db,
            request_id,
            driver_user_id=driver_user_id,
            connector_pk=connector_pk,
            status=RemoteStartStatus.NO_REPLY,
            now=utc_now_naive(),
            detail="no_reply",
        )
        if stored.status == RemoteStartStatus.STARTED:
            return stored, True
        raise RemoteStartFailure(504, "charger_timeout", "Trụ không phản hồi lệnh bắt đầu.") from exc
    except OCPPError as exc:
        stored = _finish_call(
            db,
            request_id,
            driver_user_id=driver_user_id,
            connector_pk=connector_pk,
            status=RemoteStartStatus.CHARGER_ERROR,
            now=utc_now_naive(),
            detail="charger_error",
        )
        if stored.status == RemoteStartStatus.STARTED:
            return stored, True
        raise RemoteStartFailure(502, "charger_error", "Trụ báo lỗi khi xử lý lệnh bắt đầu.") from exc
    except ConnectionError as exc:
        stored = _finish_call(
            db,
            request_id,
            driver_user_id=driver_user_id,
            connector_pk=connector_pk,
            status=RemoteStartStatus.CHARGER_ERROR,
            now=utc_now_naive(),
            detail="charger_error",
        )
        if stored.status == RemoteStartStatus.STARTED:
            return stored, True
        raise RemoteStartFailure(502, "charger_error", "Trụ đã ngắt kết nối khi xử lý lệnh.") from exc
    except Exception as exc:
        logger.warning(
            "Remote start call failed: connector_id=%s request_id=%s",
            connector_pk,
            request_id,
        )
        stored = _finish_call(
            db,
            request_id,
            driver_user_id=driver_user_id,
            connector_pk=connector_pk,
            status=RemoteStartStatus.CHARGER_ERROR,
            now=utc_now_naive(),
            detail="charger_error",
        )
        if stored.status == RemoteStartStatus.STARTED:
            return stored, True
        raise RemoteStartFailure(502, "charger_error", "Không xử lý được lệnh từ trụ.") from exc

    now = utc_now_naive()
    raw_status = result.get("status") if isinstance(result, dict) else None
    if raw_status == "Accepted":
        stored = _finish_call(
            db,
            request_id,
            driver_user_id=driver_user_id,
            connector_pk=connector_pk,
            status=RemoteStartStatus.WAITING_START,
            now=now,
            accepted=True,
            detail="accepted",
        )
        return stored, True
    if raw_status == "Rejected":
        stored = _finish_call(
            db,
            request_id,
            driver_user_id=driver_user_id,
            connector_pk=connector_pk,
            status=RemoteStartStatus.REJECTED,
            now=now,
            detail="rejected",
        )
        if stored.status == RemoteStartStatus.STARTED:
            return stored, True
        raise RemoteStartFailure(
            502,
            "rejected_by_charger",
            "Trụ từ chối lệnh; hãy kiểm tra súng đã cắm chắc chưa rồi thử lại.",
        )

    stored = _finish_call(
        db,
        request_id,
        driver_user_id=driver_user_id,
        connector_pk=connector_pk,
        status=RemoteStartStatus.CHARGER_ERROR,
        now=now,
        detail="charger_error",
    )
    if stored.status == RemoteStartStatus.STARTED:
        return stored, True
    raise RemoteStartFailure(502, "charger_error", "Trụ trả phản hồi không hợp lệ.")


def get_owned_remote_start(
    db: Session, request_id: int, driver_user_id: int
) -> tuple[RemoteStartRequest, int, datetime]:
    """Đọc yêu cầu của chính tài xế và tự hết hạn các yêu cầu chờ quá hạn."""
    now = utc_now_naive()
    lock_remote_start_writes(db, connector_id=0)
    expire_waiting_requests(db, now)
    row = (
        db.query(RemoteStartRequest)
        .filter(
            RemoteStartRequest.id == request_id,
            RemoteStartRequest.driver_user_id == driver_user_id,
        )
        .first()
    )
    db.commit()
    if row is None:
        raise RemoteStartFailure(403, "forbidden", "Bạn không có quyền xem yêu cầu này.")
    db.refresh(row)
    return row, row.connector_id, now


def resolve_pending_start(
    db: Session,
    charge_point_id: int,
    connector_number: int,
    id_tag: str,
    session_id: int,
    now: datetime | None = None,
) -> int:
    """Gắn StartTransaction vào yêu cầu tương ứng; không commit transaction."""
    now = now or utc_now_naive()
    connector = (
        db.query(Connector)
        .filter(
            Connector.charge_point_id == charge_point_id,
            Connector.connector_id == connector_number,
        )
        .first()
    )
    if connector is None:
        return 0
    connector_pk = connector.id

    # Bảo đảm Start đến sau deadline chỉ được nhận trong grace period.
    expire_waiting_requests(db, now)
    active_requests = (
        db.query(RemoteStartRequest, IdTag.id_tag)
        .join(IdTag, IdTag.id == RemoteStartRequest.id_tag_id)
        .filter(
            RemoteStartRequest.connector_id == connector_pk,
            RemoteStartRequest.status.in_(
                [RemoteStartStatus.SENDING, RemoteStartStatus.WAITING_START]
            ),
        )
        .all()
    )
    matched = next(
        (request for request, tag_value in active_requests if tag_value == id_tag),
        None,
    )
    changed = 0
    for request, _tag_value in active_requests:
        target_status = (
            RemoteStartStatus.STARTED
            if request.id == (matched.id if matched else None)
            else RemoteStartStatus.SUPERSEDED
        )
        result = db.execute(
            update(RemoteStartRequest)
            .where(
                RemoteStartRequest.id == request.id,
                RemoteStartRequest.status.in_(
                    [RemoteStartStatus.SENDING, RemoteStartStatus.WAITING_START]
                ),
            )
            .values(
                status=target_status,
                session_id=session_id if target_status == RemoteStartStatus.STARTED else None,
                resolved_at=now,
                detail=None if target_status == RemoteStartStatus.STARTED else "superseded",
            )
            .execution_options(synchronize_session=False)
        )
        changed += int(cast(CursorResult[Any], result).rowcount or 0)

    if matched is not None:
        return changed

    cutoff = now - timedelta(seconds=settings.REMOTE_START_LATE_GRACE)
    latest_same_tag = (
        db.query(RemoteStartRequest)
        .join(IdTag, IdTag.id == RemoteStartRequest.id_tag_id)
        .filter(
            RemoteStartRequest.connector_id == connector_pk,
            IdTag.id_tag == id_tag,
        )
        .order_by(RemoteStartRequest.created_at.desc(), RemoteStartRequest.id.desc())
        .first()
    )
    if (
        latest_same_tag is not None
        and latest_same_tag.status == RemoteStartStatus.EXPIRED
        and latest_same_tag.created_at >= cutoff
    ):
        result = db.execute(
            update(RemoteStartRequest)
            .where(
                RemoteStartRequest.id == latest_same_tag.id,
                RemoteStartRequest.status == RemoteStartStatus.EXPIRED,
            )
            .values(
                status=RemoteStartStatus.STARTED,
                session_id=session_id,
                resolved_at=now,
                detail="late_start",
            )
            .execution_options(synchronize_session=False)
        )
        changed += int(cast(CursorResult[Any], result).rowcount or 0)
    return changed
