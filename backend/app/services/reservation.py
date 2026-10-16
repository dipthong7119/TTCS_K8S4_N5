"""
Services: reservations (SCRUM-76 / S-48: Nghiệp vụ đặt chỗ trụ sạc).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.charge_point import ChargePoint, Connector
from app.models.id_tag import IdTag
from app.models.reservation import Reservation
from app.models.station import Station
from app.models.user import User
from app.schemas.reservation import (
    AlternativeSuggestion,
    ReservationCreateRequest,
    ReservationCreateResponse,
    ReservationItem,
)
from app.services.audit import record_remote_command
from app.services.connection_manager import manager
from app.services.ocpp_handlers import publish_charge_point_status
from app.services.ocpp_parser import OCPPError
from app.services.ocpp_status import is_charge_point_stale
from app.services.wallet import has_minimum_balance

logger = logging.getLogger(__name__)


def resolve_driver_id_tag(
    db: Session,
    user: User,
    requested_tag: str | None = None,
) -> IdTag:
    """Xác định bản ghi thẻ sạc hợp lệ cho tài xế."""
    if requested_tag:
        tag_record = (
            db.query(IdTag)
            .filter(IdTag.id_tag == requested_tag)
            .first()
        )
        if not tag_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã thẻ sạc không tồn tại trên hệ thống.",
            )
        if tag_record.is_blocked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thẻ sạc đang bị khóa, không thể sử dụng để đặt chỗ.",
            )
        # Nếu không phải admin/operator thì chỉ được dùng thẻ của chính mình
        user_roles = [r.name for r in user.roles]
        if (
            "admin" not in user_roles
            and "operator" not in user_roles
            and tag_record.user_id != user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền sử dụng thẻ sạc này.",
            )
        return tag_record

    # Không truyền tag -> tìm thẻ của user (ưu tiên thẻ ảo is_virtual=True hoặc thẻ chưa bị khóa)
    tag_record = (
        db.query(IdTag)
        .filter(IdTag.user_id == user.id, IdTag.is_blocked.is_(False))
        .order_by(IdTag.is_virtual.desc(), IdTag.created_at.desc())
        .first()
    )
    if not tag_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài xế chưa có thẻ sạc (idTag) khả dụng để thực hiện đặt chỗ.",
        )
    return tag_record


def validate_reservation_times(
    start_time: datetime | None,
    expiry_date: datetime | None,
    expiry_minutes: int | None,
) -> tuple[datetime, datetime]:
    """Kiểm tra và chuẩn hóa mốc thời gian đặt chỗ theo đặc tả S-48.
    
    Quy tắc:
    - Bắt đầu trong vòng 2 giờ tới.
    - Thời lượng giữ chỗ tối đa 2 giờ (120 phút), mặc định 30 phút.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Xác định start_time
    if start_time is None:
        start = now
    else:
        # Chuyển về naive UTC nếu có tzinfo
        start = (
            start_time.astimezone(timezone.utc).replace(tzinfo=None)
            if start_time.tzinfo
            else start_time
        )
        # Không cho phép đặt trong quá khứ quá 5 phút
        if start < now - timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Thời gian bắt đầu đặt chỗ không được ở trong quá khứ.",
            )
        # Giới hạn đặt trong vòng 2 giờ tới
        if start > now + timedelta(hours=2, minutes=5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Chỉ được phép đặt chỗ trước trong vòng 2 giờ tới.",
            )

    # 2. Xác định expiry_date
    if expiry_date is not None:
        expiry = (
            expiry_date.astimezone(timezone.utc).replace(tzinfo=None)
            if expiry_date.tzinfo
            else expiry_date
        )
    elif expiry_minutes is not None:
        expiry = start + timedelta(minutes=expiry_minutes)
    else:
        expiry = start + timedelta(minutes=30)

    if expiry <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thời hạn giữ chỗ phải lớn hơn thời gian bắt đầu.",
        )

    if expiry > start + timedelta(hours=2, minutes=1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thời lượng giữ chỗ tối đa không quá 2 giờ.",
        )

    return start, expiry


def lock_connector_for_reservation(db: Session, connector_pk: int) -> None:
    """Khóa bản ghi đầu nối ở tầng CSDL để tuần tự hóa các yêu cầu cạnh tranh (SCRUM-77 / S-49).
    
    SQLite: BEGIN IMMEDIATE khóa file ghi cơ sở dữ liệu ngay lập tức.
    PostgreSQL / dialect khác: SELECT ... FOR UPDATE trên bản ghi Connector.
    """
    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        connection = db.connection()
        raw_connection = connection.connection.driver_connection
        if raw_connection is not None and not raw_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        return
    db.execute(
        select(Connector.id)
        .where(Connector.id == connector_pk)
        .with_for_update()
    ).first()


def expire_stale_reservations(db: Session, now: datetime) -> int:
    """Expire unconfirmed ReserveNow requests without charging a no-show fee."""
    result = db.execute(
        update(Reservation)
        .where(
            Reservation.status == "pending",
            Reservation.expiry_date <= now,
        )
        .values(
            status="expired",
            reject_reason="expired",
            expired_at=now,
        )
        .execution_options(synchronize_session="fetch")
    )
    return int(cast(CursorResult[Any], result).rowcount or 0)


def find_alternative_connectors(
    db: Session,
    current_charge_point_id: int,
    current_connector_id: int,
    limit: int = 3,
) -> list[AlternativeSuggestion]:
    """Tìm các đầu nối khả dụng khác để gợi ý cho tài xế khi bị trùng đặt chỗ (SCRUM-77 / S-49).

    Ưu tiên:
    1. Đầu nối khác trên cùng trạm sạc (cùng trụ hoặc trụ khác trong trạm).
    2. Đầu nối tại các trạm đang hoạt động khác.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    current_cp = (
        db.query(ChargePoint)
        .filter(ChargePoint.id == current_charge_point_id)
        .first()
    )
    if not current_cp:
        return []

    station_id = current_cp.station_id

    # Danh sách ID các cặp (trụ, đầu nối) đã có đặt chỗ active
    active_reserved_pairs = set(
        db.query(Reservation.charge_point_id, Reservation.connector_id)
        .filter(
            Reservation.status.in_(["accepted", "pending"]),
            Reservation.expiry_date > now,
        )
        .all()
    )

    busy_statuses = {
        "charging",
        "suspended_ev",
        "suspended_evse",
        "finishing",
        "reserved",
        "faulted",
        "unavailable",
    }
    busy_ocpp = {
        "Charging",
        "SuspendedEV",
        "SuspendedEVSE",
        "Finishing",
        "Reserved",
        "Faulted",
        "Unavailable",
        "Occupied",
    }

    suggestions: list[AlternativeSuggestion] = []

    # 1. Tìm trong cùng trạm sạc trước
    same_station_cps = (
        db.query(ChargePoint, Station)
        .join(Station, ChargePoint.station_id == Station.id)
        .filter(
            ChargePoint.station_id == station_id,
            ChargePoint.status == "online",
            Station.status == "active",
        )
        .all()
    )

    for cp, st in same_station_cps:
        if (
            cp.code not in manager.active_connections
            or is_charge_point_stale(cp.last_seen_at)
        ):
            continue
        for conn in cp.connectors:
            if (
                cp.id == current_charge_point_id
                and conn.connector_id == current_connector_id
            ):
                continue
            if conn.status.lower() in busy_statuses or (
                conn.ocpp_status and conn.ocpp_status in busy_ocpp
            ):
                continue
            if (cp.id, conn.connector_id) in active_reserved_pairs:
                continue
            suggestions.append(
                AlternativeSuggestion(
                    station_id=st.id,
                    station_name=st.name,
                    station_address=st.address,
                    charge_point_id=cp.id,
                    charge_point_code=cp.code,
                    connector_id=conn.connector_id,
                    connector_status=conn.status,
                )
            )
            if len(suggestions) >= limit:
                return suggestions

    # 2. Nếu vẫn chưa đủ, tìm ở các trạm active khác
    other_cps = (
        db.query(ChargePoint, Station)
        .join(Station, ChargePoint.station_id == Station.id)
        .filter(
            ChargePoint.station_id != station_id,
            ChargePoint.status == "online",
            Station.status == "active",
        )
        .limit(limit * 2)
        .all()
    )

    for cp, st in other_cps:
        if (
            cp.code not in manager.active_connections
            or is_charge_point_stale(cp.last_seen_at)
        ):
            continue
        for conn in cp.connectors:
            if conn.status.lower() in busy_statuses or (
                conn.ocpp_status and conn.ocpp_status in busy_ocpp
            ):
                continue
            if (cp.id, conn.connector_id) in active_reserved_pairs:
                continue
            suggestions.append(
                AlternativeSuggestion(
                    station_id=st.id,
                    station_name=st.name,
                    station_address=st.address,
                    charge_point_id=cp.id,
                    charge_point_code=cp.code,
                    connector_id=conn.connector_id,
                    connector_status=conn.status,
                )
            )
            if len(suggestions) >= limit:
                return suggestions

    return suggestions


def build_conflict_detail(
    db: Session,
    charge_point: ChargePoint,
    connector_id: int,
    message: str = "Đầu nối đã có người đặt trước trong khoảng thời gian này.",
    code: str = "connector_already_reserved",
) -> dict[str, Any]:
    """Tạo payload chi tiết lỗi 409 kèm gợi ý các trụ/đầu nối khả dụng khác (SCRUM-77 / S-49)."""
    suggestions = find_alternative_connectors(db, charge_point.id, connector_id)
    return {
        "message": message,
        "code": code,
        "charge_point_code": charge_point.code,
        "connector_id": connector_id,
        "suggestions": [s.model_dump() for s in suggestions],
    }


async def create_reservation(
    db: Session,
    user: User,
    payload: ReservationCreateRequest,
) -> ReservationCreateResponse:
    """Tạo đặt chỗ trụ sạc và gửi lệnh ReserveNow xuống trụ sạc (SCRUM-76 / S-48)."""
    # 1. Kiểm tra trụ sạc
    point = (
        db.query(ChargePoint)
        .filter(ChargePoint.code == payload.charge_point_code)
        .first()
    )
    if point is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy trụ sạc.",
        )

    # 2. Kiểm tra đầu nối
    connector = (
        db.query(Connector)
        .filter(
            Connector.charge_point_id == point.id,
            Connector.connector_id == payload.connector_id,
        )
        .first()
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đầu nối trên trụ sạc.",
        )

    # 3. Kiểm tra trụ online
    if (
        point.code not in manager.active_connections
        or point.status != "online"
        or is_charge_point_stale(point.last_seen_at)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trụ sạc đang ngoại tuyến, không thể nhận lệnh đặt chỗ.",
        )

    # 4. Kiểm tra trạng thái đầu nối khả dụng
    busy_statuses = {
        "charging",
        "suspended_ev",
        "suspended_evse",
        "finishing",
        "reserved",
        "faulted",
        "unavailable",
    }
    busy_ocpp_statuses = {
        "Charging",
        "SuspendedEV",
        "SuspendedEVSE",
        "Finishing",
        "Reserved",
        "Faulted",
        "Unavailable",
        "Occupied",
    }
    if (
        connector.status.lower() in busy_statuses
        or (connector.ocpp_status and connector.ocpp_status in busy_ocpp_statuses)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Đầu nối đang bận hoặc không khả dụng (trạng thái: {connector.status}).",
        )

    # 5. Kiểm tra ví tài xế có đủ số dư tối thiểu
    if not has_minimum_balance(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số dư ví không đủ ngưỡng tối thiểu để thực hiện đặt chỗ.",
        )

    # 6. Xác thực id_tag & thời gian
    id_tag_record = resolve_driver_id_tag(db, user, payload.id_tag)
    id_tag = id_tag_record.id_tag
    start_time, expiry_date = validate_reservation_times(
        payload.start_time, payload.expiry_date, payload.expiry_minutes
    )

    # 7. Khóa đầu nối tại CSDL và kiểm tra trùng lịch đặt chỗ đã có hiệu lực (SCRUM-77 / S-49)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    from app.services.reservations import expire_due_for_connector, snapshot_no_show_fee

    expire_due_for_connector(db, connector.id, now)
    expire_stale_reservations(db, now)
    db.commit()
    lock_connector_for_reservation(db, connector.id)

    existing_reservation = (
        db.query(Reservation)
        .filter(
            Reservation.charge_point_id == point.id,
            Reservation.connector_id == payload.connector_id,
            Reservation.status.in_(["accepted", "pending"]),
            Reservation.expiry_date > now,
        )
        .first()
    )
    if existing_reservation is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_conflict_detail(db, point, payload.connector_id),
        )

    # 8. Tạo bản ghi reservation ở trạng thái pending (được bảo vệ bởi partial unique index CSDL)
    reservation = Reservation(
        charge_point_id=point.id,
        connector_id=payload.connector_id,
        connector_db_id=connector.id,
        user_id=user.id,
        id_tag=id_tag,
        id_tag_id=id_tag_record.id,
        start_time=start_time,
        expiry_date=expiry_date,
        status="pending",
        no_show_fee_vnd=snapshot_no_show_fee(db, point.station_id),
    )
    db.add(reservation)
    try:
        db.flush()
        reservation_id = int(reservation.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_conflict_detail(db, point, payload.connector_id),
        ) from exc

    masked_tag = id_tag[-4:] if len(id_tag) >= 4 else "****"
    logger.info(
        "Sending OCPP ReserveNow: reservation_id=%s charge_point=%s connector_id=%s id_tag=%s expiry=%s",
        reservation_id,
        point.code,
        payload.connector_id,
        masked_tag,
        expiry_date.isoformat(),
    )

    # 9. Gửi lệnh ReserveNow xuống trụ sạc
    ocpp_payload = {
        "connectorId": payload.connector_id,
        "expiryDate": expiry_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "idTag": id_tag,
        "reservationId": reservation_id,
    }

    def record_reservation_outcome(action: str, outcome: str) -> None:
        record_remote_command(
            db,
            action=action,
            command="ReserveNow",
            object_type="reservation",
            object_id=reservation_id,
            actor=user,
            charge_point_code=point.code,
            outcome=outcome,
            details={
                "connector_id": payload.connector_id,
                "expiry_date": expiry_date.isoformat(),
                "id_tag_masked": masked_tag,
            },
        )
        db.commit()

    try:
        result = await manager.send_call(
            point.code,
            "ReserveNow",
            ocpp_payload,
            timeout=settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        reservation.status = "rejected"
        reservation.reject_reason = "timeout"
        record_reservation_outcome("reservation.failed", "timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Trụ sạc không phản hồi lệnh ReserveNow trong thời gian chờ.",
        ) from exc
    except ConnectionError as exc:
        reservation.status = "rejected"
        reservation.reject_reason = "disconnected"
        record_reservation_outcome("reservation.failed", "disconnected")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trụ sạc đã ngắt kết nối trước khi nhận lệnh đặt chỗ.",
        ) from exc
    except OCPPError as exc:
        reservation.status = "rejected"
        reservation.reject_reason = "call_error"
        record_reservation_outcome("reservation.rejected", "call_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Trụ từ chối hoặc báo lỗi cú pháp khi đặt chỗ.",
        ) from exc

    raw_status = result.get("status") if isinstance(result, dict) else None

    # 10. Xử lý phản hồi từ trụ sạc
    if raw_status == "Accepted":
        reservation.status = "accepted"
        connector.status = "reserved"
        connector.ocpp_status = "Reserved"
        record_reservation_outcome("reservation.accepted", "Accepted")
        publish_charge_point_status(db, point.id)

        item = ReservationItem(
            id=reservation_id,
            charge_point_id=point.id,
            charge_point_code=point.code,
            connector_id=payload.connector_id,
            user_id=user.id,
            id_tag=id_tag,
            start_time=start_time,
            expiry_date=expiry_date,
            status="accepted",
            reject_reason=None,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            expired_at=reservation.expired_at,
            cancelled_at=reservation.cancelled_at,
            no_show_fee_vnd=reservation.no_show_fee_vnd,
            cancel_status=reservation.cancel_status,
        )
        return ReservationCreateResponse(
            status="Accepted",
            message="Đặt chỗ thành công. Chỗ sạc đã được giữ cho bạn.",
            reservation=item,
        )

    # Trụ phản hồi Occupied, Faulted, Unavailable, Rejected...
    status_str = str(raw_status) if raw_status is not None else "Rejected"
    reservation.status = "rejected"
    reservation.reject_reason = status_str
    record_reservation_outcome("reservation.rejected", reservation.reject_reason)

    reason_mapping: dict[str, str] = {
        "Occupied": "Trụ sạc báo đầu nối đang bận (Occupied).",
        "Faulted": "Trụ sạc đang gặp sự cố (Faulted).",
        "Unavailable": "Đầu nối hiện không khả dụng (Unavailable).",
        "Rejected": "Trụ sạc từ chối nhận lệnh đặt chỗ (Rejected).",
    }
    reason_msg = reason_mapping.get(status_str, f"Trụ sạc từ chối đặt chỗ: {status_str}")

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=reason_msg,
    )


def get_user_reservations(
    db: Session,
    user: User,
    active_only: bool = False,
) -> list[ReservationItem]:
    """Lấy danh sách các lượt đặt chỗ của tài xế."""
    query = (
        db.query(Reservation, ChargePoint.code.label("charge_point_code"))
        .join(ChargePoint, Reservation.charge_point_id == ChargePoint.id)
        .filter(Reservation.user_id == user.id)
    )
    if active_only:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        query = query.filter(
            Reservation.status == "accepted",
            Reservation.expiry_date > now,
        )
    rows = query.order_by(Reservation.created_at.desc()).all()

    items: list[ReservationItem] = []
    for res, cp_code in rows:
        items.append(
            ReservationItem(
                id=res.id,
                charge_point_id=res.charge_point_id,
                charge_point_code=cp_code,
                connector_id=res.connector_id,
                user_id=res.user_id,
                id_tag=res.id_tag,
                start_time=res.start_time,
                expiry_date=res.expiry_date,
                status=res.status,
                reject_reason=res.reject_reason,
                created_at=res.created_at,
                expired_at=res.expired_at,
                cancelled_at=res.cancelled_at,
                no_show_fee_vnd=res.no_show_fee_vnd,
                cancel_status=res.cancel_status,
            )
        )
    return items


def get_reservation_by_id(
    db: Session,
    user: User,
    reservation_id: int,
) -> ReservationItem:
    """Xem chi tiết một lượt đặt chỗ."""
    row = (
        db.query(Reservation, ChargePoint.code.label("charge_point_code"))
        .join(ChargePoint, Reservation.charge_point_id == ChargePoint.id)
        .filter(Reservation.id == reservation_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bản ghi đặt chỗ.",
        )
    res, cp_code = row
    user_roles = [r.name for r in user.roles]
    if "admin" not in user_roles and "operator" not in user_roles and res.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập thông tin đặt chỗ này.",
        )

    return ReservationItem(
        id=res.id,
        charge_point_id=res.charge_point_id,
        charge_point_code=cp_code,
        connector_id=res.connector_id,
        user_id=res.user_id,
        id_tag=res.id_tag,
        start_time=res.start_time,
        expiry_date=res.expiry_date,
        status=res.status,
        reject_reason=res.reject_reason,
        created_at=res.created_at,
        expired_at=res.expired_at,
        cancelled_at=res.cancelled_at,
        no_show_fee_vnd=res.no_show_fee_vnd,
        cancel_status=res.cancel_status,
    )
