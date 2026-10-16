"""Nghiệp vụ đặt chỗ quá hạn (S-52): hàm thuần, expire_reservation, mark_reservation_fulfilled.

Thiết kế:
- Mọi so sánh thời gian dùng UTC naive (không có tzinfo), nhất quán với các module khác.
- Tất cả tiền là int (VNĐ), không dùng float.
- expire_reservation: một transaction ngắn, commit xong mới gửi OCPP.
- mark_reservation_fulfilled: gọi từ StartTransaction trong cùng transaction của nó.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import status
from sqlalchemy import and_, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.reservation import CancelStatus, Reservation, ReservationStatus
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.audit import append_audit
from app.services.connection_manager import manager
from app.services.ocpp_parser import OCPPError

logger = logging.getLogger(__name__)


# ── Hàm thuần (không phụ thuộc DB hay mạng) ──────────────────────────────────


def is_overdue(
    reservation: "Reservation",
    now: datetime,
    grace_seconds: int,
) -> bool:
    """Kiểm tra đặt chỗ đã quá hạn cộng ân hạn chưa.

    Args:
        reservation: Đặt chỗ cần kiểm tra.
        now: Thời điểm hiện tại (UTC naive).
        grace_seconds: Ân hạn tính bằng giây.

    Returns:
        True nếu now >= expiry_at + grace_seconds.
    """
    expiry_naive = reservation.expiry_at
    if expiry_naive is None:
        return False
    # Đảm bảo naive
    if hasattr(expiry_naive, "tzinfo") and expiry_naive.tzinfo is not None:
        expiry_naive = expiry_naive.astimezone(UTC).replace(tzinfo=None)
    deadline = expiry_naive.timestamp() + grace_seconds
    now_ts = now.timestamp()
    return now_ts >= deadline


def decide_fee(
    reservation: "Reservation",
    station_fee_vnd: int,
    driver_prior_no_shows: int,
    first_free_enabled: bool,
) -> tuple[int, str | None]:
    """Tính phí không đến và lý do miễn (nếu có).

    Args:
        reservation: Đặt chỗ đã quá hạn.
        station_fee_vnd: Mức phí hiện tại của trạm (đơn vị đồng VNĐ).
        driver_prior_no_shows: Số lần tài xế đã bị tính phí no-show trước đây.
        first_free_enabled: Có cho phép miễn phí lần đầu không.

    Returns:
        (amount_vnd, waived_reason):
            - amount_vnd >= 0 (int). 0 khi miễn.
            - waived_reason: chuỗi lý do miễn (AC8) hoặc None.
    """
    # Mức phí chốt lúc đặt ưu tiên; nếu None thì dùng mức hiện tại của trạm
    fee = reservation.no_show_fee_vnd
    if fee is None:
        fee = station_fee_vnd

    if fee <= 0:
        return 0, None

    # AC8: miễn phí lần đầu nếu được bật và chưa có lần nào
    if first_free_enabled and driver_prior_no_shows == 0:
        return 0, "first_no_show_waived"

    return fee, None


# ── Truy vấn phụ trợ ──────────────────────────────────────────────────────────


def _count_prior_no_shows(db: Session, driver_user_id: int) -> int:
    """Đếm số đặt chỗ expired đã bị tính phí trước đây (fee_ledger_entry_id IS NOT NULL)."""
    return (
        db.query(Reservation)
        .filter(
            Reservation.driver_user_id == driver_user_id,
            Reservation.status == ReservationStatus.EXPIRED,
            Reservation.fee_ledger_entry_id.isnot(None),
        )
        .count()
    )


def _get_station_fee_for_connector(db: Session, connector_id: int | None) -> int:
    """Lấy no_show_fee_vnd của trạm chứa đầu nối."""
    from app.models.charge_point import ChargePoint, Connector
    from app.models.station import Station

    if connector_id is None:
        return 0
    row = (
        db.query(Station.no_show_fee_vnd)
        .join(ChargePoint, ChargePoint.station_id == Station.id)
        .join(Connector, Connector.charge_point_id == ChargePoint.id)
        .filter(Connector.id == connector_id)
        .first()
    )
    if row is None:
        return 0
    return int(row[0] or 0)


def snapshot_no_show_fee(db: Session, station_id: int) -> int:
    """Chốt mức phí không đến tại thời điểm đặt chỗ (gọi từ S-48 khi tạo đặt chỗ).

    Hàm này để đường tạo đặt chỗ (S-48) dùng khi tạo Reservation.no_show_fee_vnd.
    """
    from app.models.station import Station

    row = db.query(Station.no_show_fee_vnd).filter(Station.id == station_id).first()
    if row is None:
        return 0
    return int(row[0] or 0)


def set_no_show_fee(db: Session, station_id: int, fee_vnd: int) -> None:
    """Đặt mức phí không đến cho trạm (dùng trong seed và test, không dùng API).

    Args:
        db: Session database.
        station_id: ID trạm.
        fee_vnd: Mức phí mới (>= 0, đồng VNĐ).
    """
    from app.models.station import Station

    if fee_vnd < 0:
        raise ValueError("no_show_fee_vnd phải >= 0")
    db.execute(
        update(Station)
        .where(Station.id == station_id)
        .values(no_show_fee_vnd=fee_vnd)
    )


# ── Hàm trừ ví cho phí không đến ─────────────────────────────────────────────


def _deduct_no_show_fee(
    db: Session,
    user_id: int,
    reservation_id: int,
    amount_vnd: int,
) -> WalletLedgerEntry:
    """Trừ ví tài xế phí không đến trong cùng transaction của expire_reservation.

    Dùng idempotency_key để bảo vệ trùng ghi ở tầng ứng dụng.
    UNIQUE (user_id, idempotency_key) ở DB là lớp bảo vệ cuối.

    Args:
        db: Session đang mở (caller phải commit).
        user_id: ID tài xế.
        reservation_id: ID đặt chỗ (dùng làm reference).
        amount_vnd: Số tiền dương (sẽ ghi âm vào sổ cái).

    Returns:
        WalletLedgerEntry đã flush.
    """
    idem_key = f"no-show-fee:{reservation_id}"
    receipt = f"RES-{reservation_id}"

    # Tầng bảo vệ ứng dụng: tìm xem đã ghi chưa
    existing = db.query(WalletLedgerEntry).filter_by(idempotency_key=idem_key).first()
    if existing:
        return existing

    entry = WalletLedgerEntry(
        user_id=user_id,
        entry_type="no_show_fee",
        amount_vnd=-abs(amount_vnd),     # luôn âm
        idempotency_key=idem_key,
        receipt_code=receipt,
        reference_type="reservation",
        reference_id=reservation_id,
        # Mô tả không chứa dữ liệu vị trí nhạy cảm (NĐ 13/2023)
        description=f"Phí không đến cho đặt chỗ #{reservation_id}",
        actor_id=None,  # hệ thống tự động, không có actor người dùng
    )
    db.add(entry)
    db.flush()
    return entry


# ── Hàm xử lý một đặt chỗ ────────────────────────────────────────────────────


def expire_reservation(
    db: Session,
    reservation_id: int,
    now: datetime,
) -> bool:
    """Xử lý một đặt chỗ quá hạn: chuyển expired, trừ ví, ghi nhật ký.

    Thực hiện trong MỘT transaction ngắn. Sau khi commit, caller tự gửi
    CancelReservation (không giữ transaction trong lúc chờ trụ).

    Args:
        db: Session mở sẵn (hàm tự commit/rollback).
        reservation_id: ID đặt chỗ cần xử lý.
        now: Thời điểm hiện tại (UTC naive).

    Returns:
        True nếu đã chuyển trạng thái và commit thành công.
        False nếu idempotent skip (đã xử lý rồi hoặc đã fulfilled).
    """
    grace = settings.NO_SHOW_GRACE_SECONDS

    # ─ a) Giành quyền chuyển trạng thái bằng UPDATE có điều kiện ─────────────
    # SQLite: BEGIN IMMEDIATE sẽ được thực hiện tự động khi UPDATE chạm dữ liệu.
    # Điều kiện expiry_at + grace <= now viết dưới dạng EPOCH để tránh hàm datetime tùy dialect.
    # Thay vào đó dùng phép tính Python:
    # "WHERE id = :id AND status = 'active'"
    # và kiểm tra is_overdue ngay sau khi load row — đảm bảo race-condition an toàn
    # vì SQLite là single-writer.
    #
    # Cách an toàn nhất với SQLite (single-writer): load row rồi UPDATE có điều kiện.
    res = db.get(Reservation, reservation_id)
    if res is None:
        return False
    if res.status != ReservationStatus.ACTIVE:
        return False  # đã xử lý hoặc đã fulfilled: idempotent skip
    if not is_overdue(res, now, grace):
        return False  # chưa tới hạn

    # Giành quyền bằng UPDATE có điều kiện (rowcount = 0 → ai đó nhanh hơn)
    result = db.execute(
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.status == ReservationStatus.ACTIVE,
        )
        .values(
            status=ReservationStatus.EXPIRED,
            expired_at=now,
            cancel_status=CancelStatus.PENDING,
        )
    )
    if result.rowcount == 0:
        db.rollback()
        return False

    # Reload sau UPDATE để có giá trị mới nhất
    db.expire(res)
    res = db.get(Reservation, reservation_id)
    if res is None:
        db.rollback()
        return False

    # ─ b) Tính phí ────────────────────────────────────────────────────────────
    station_fee = _get_station_fee_for_connector(db, res.connector_db_id)
    prior_count = _count_prior_no_shows(db, res.driver_user_id)
    fee_amount, waived_reason = decide_fee(
        res,
        station_fee,
        prior_count,
        settings.NO_SHOW_FIRST_FREE,
    )

    ledger_entry: WalletLedgerEntry | None = None
    if fee_amount > 0:
        # ─ c) Trừ ví — chống trùng nhờ UNIQUE idempotency_key ────────────────
        try:
            ledger_entry = _deduct_no_show_fee(
                db, res.driver_user_id, reservation_id, fee_amount
            )
        except IntegrityError:
            # UNIQUE violation → đã trừ rồi (lần chạy khác commit sớm hơn)
            db.rollback()
            logger.info(
                "no_show_fee đã ghi trước, skip: reservation=%s",
                reservation_id,
            )
            return False

        # Cập nhật fee_ledger_entry_id và no_show_fee_vnd (số tiền thực tế trừ)
        db.execute(
            update(Reservation)
            .where(Reservation.id == reservation_id)
            .values(
                fee_ledger_entry_id=ledger_entry.id,
                no_show_fee_vnd=fee_amount,
            )
        )
    elif waived_reason:
        # AC8: miễn phí lần đầu — ghi lý do, không ghi sổ cái
        db.execute(
            update(Reservation)
            .where(Reservation.id == reservation_id)
            .values(fee_waived_reason=waived_reason)
        )

    # ─ d) Ghi nhật ký (T-57) ─────────────────────────────────────────────────
    append_audit(
        db,
        action="reservation.expired",
        object_type="reservation",
        object_id=reservation_id,
        actor_id=None,  # hệ thống
        details={
            "connector_id": res.connector_id,
            "fee_vnd": fee_amount,
            "waived_reason": waived_reason,
            "cancel_status": CancelStatus.PENDING.value,
        },
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning(
            "Commit expire_reservation thất bại (có thể trùng sổ cái): reservation=%s",
            reservation_id,
        )
        return False

    logger.info(
        "reservation.expired: id=%s connector=%s fee_vnd=%s waived=%s",
        reservation_id,
        res.connector_id,
        fee_amount,
        waived_reason,
    )
    return True


# ── Hàm gửi CancelReservation và cập nhật cancel_status ──────────────────────


async def send_cancel_reservation(
    db: Session,
    reservation_id: int,
    charge_point_code: str,
) -> str:
    """Gửi CancelReservation xuống trụ và cập nhật cancel_status.

    Không giữ transaction trong lúc chờ trụ trả lời.
    Chỉ được gọi SAU KHI expire_reservation đã commit (cancel_status = pending).

    Returns:
        cancel_status sau khi xử lý: "done" | "gone" | "pending" (retry sau).
    """

    new_status: CancelStatus
    now = datetime.now(UTC).replace(tzinfo=None)

    try:
        result = await manager.send_call(
            charge_point_code,
            "CancelReservation",
            {"reservationId": reservation_id},
            timeout=float(settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS),
        )
        ocpp_status = result.get("status", "")
        if ocpp_status == "Accepted":
            new_status = CancelStatus.DONE
        else:
            # Rejected → trụ không còn biết chỗ này (đã tự nhả) → coi như xong
            logger.warning(
                "CancelReservation Rejected bởi trụ (trụ đã tự nhả chỗ): "
                "id=%s cp=%s",
                reservation_id,
                charge_point_code,
            )
            new_status = CancelStatus.GONE
    except (ConnectionError, TimeoutError, OCPPError, Exception):
        # Trụ ngoại tuyến, timeout, CALLERROR → giữ pending, tăng cancel_attempts
        new_status = CancelStatus.PENDING

    # Cập nhật cancel_status bằng UPDATE có điều kiện (chỉ khi vẫn pending)
    values: dict = {"last_cancel_attempt_at": now}
    if new_status in (CancelStatus.DONE, CancelStatus.GONE):
        values["cancel_status"] = new_status
    else:
        # pending: tăng số lần thử
        values["cancel_attempts"] = Reservation.cancel_attempts + 1

    db.execute(
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.cancel_status == CancelStatus.PENDING,
        )
        .values(**values)
    )
    db.commit()

    logger.info(
        "CancelReservation: id=%s cp=%s result=%s",
        reservation_id,
        charge_point_code,
        new_status.value,
    )
    return new_status.value


# ── Hàm tiện ích cho đầu nối (S-48 / RemoteStart dùng sau) ──────────────────


def expire_due_for_connector(
    db: Session,
    connector_id: int,
    now: datetime,
) -> list[int]:
    """Xử lý ngay các đặt chỗ quá hạn trên một đầu nối cụ thể.

    Gọi từ đường tạo đặt chỗ (S-48) hoặc RemoteStart để tránh chỗ cũ chặn người mới
    khi job chưa kịp chạy. Chỉ cung cấp hàm; caller tự tích hợp.

    Returns:
        Danh sách reservation_id đã xử lý thành công.
    """
    grace = settings.NO_SHOW_GRACE_SECONDS
    from app.models.charge_point import Connector

    connector = db.get(Connector, connector_id)
    if connector is None:
        return []
    connector_filter = or_(
        Reservation.connector_db_id == connector_id,
        and_(
            Reservation.connector_db_id.is_(None),
            Reservation.charge_point_id == connector.charge_point_id,
            Reservation.connector_id == connector.connector_id,
        ),
    )
    rows = (
        db.query(Reservation.id, Reservation.expiry_at)
        .filter(
            connector_filter,
            Reservation.status == ReservationStatus.ACTIVE,
        )
        .all()
    )
    processed = []
    for row in rows:
        res_id, expiry_at = row
        # Kiểm tra quá hạn thủ công để tránh import vòng
        exp_naive = expiry_at
        if hasattr(exp_naive, "tzinfo") and exp_naive.tzinfo is not None:
            exp_naive = exp_naive.astimezone(UTC).replace(tzinfo=None)
        deadline_ts = exp_naive.timestamp() + grace
        if now.timestamp() >= deadline_ts:
            try:
                ok = expire_reservation(db, res_id, now)
                if ok:
                    processed.append(res_id)
            except Exception:
                logger.exception(
                    "expire_due_for_connector lỗi: connector=%s reservation=%s",
                    connector_id,
                    res_id,
                )
    return processed


# ── Hoàn thành đặt chỗ ở StartTransaction ────────────────────────────────────


def mark_reservation_fulfilled(
    db: Session,
    connector_id: int,
    id_tag_id: int | None,
    session_id: int,
    reservation_id: int | None = None,
) -> bool:
    """Đánh dấu đặt chỗ là fulfilled khi tài xế bắt đầu phiên.

    Phải được gọi trong cùng transaction với việc tạo ChargingSession,
    trong begin_nested() để lỗi không làm hỏng phiên.

    Args:
        db: Session đang mở (caller quản lý commit).
        connector_id: ID đầu nối (db id, không phải OCPP connector_id).
        id_tag_id: ID thẻ dùng khi bắt đầu phiên (None nếu không xác định được).
        session_id: ID phiên vừa tạo.
        reservation_id: reservationId trong StartTransaction payload (None nếu không có).

    Returns:
        True nếu đã fulfilled thành công, False nếu không khớp hoặc đã xử lý.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    from app.models.charge_point import Connector

    connector = db.get(Connector, connector_id)
    if connector is None:
        return False
    connector_filter = or_(
        Reservation.connector_db_id == connector_id,
        and_(
            Reservation.connector_db_id.is_(None),
            Reservation.charge_point_id == connector.charge_point_id,
            Reservation.connector_id == connector.connector_id,
        ),
    )

    # Tìm đặt chỗ active
    if reservation_id is not None:
        # Khớp theo reservationId, kiểm tra thêm đầu nối và thẻ
        res = (
            db.query(Reservation)
            .filter(
                Reservation.id == reservation_id,
                connector_filter,
                Reservation.status == ReservationStatus.ACTIVE,
            )
            .first()
        )
        if res is not None and id_tag_id is not None and res.id_tag_id != id_tag_id:
            # Thẻ khác → không khớp; trụ tự từ chối theo đặc tả OCPP
            logger.warning(
                "StartTransaction thẻ khác với người đặt: reservation=%s id_tag_id=%s expected=%s",
                reservation_id,
                id_tag_id,
                res.id_tag_id,
            )
            return False
        if res is None:
            # reservationId tìm không thấy active → kiểm tra xem đã expired chưa
            expired_res = db.get(Reservation, reservation_id)
            if expired_res is not None and expired_res.status == ReservationStatus.EXPIRED:
                logger.warning(
                    "StartTransaction tới sau khi reservation đã expired và bị tính phí: "
                    "reservation=%s session=%s — CẦN XỬ LÝ TAY nếu muốn hoàn phí",
                    reservation_id,
                    session_id,
                )
            return False
    else:
        # Không có reservationId → khớp theo đầu nối và thẻ của tài xế
        if id_tag_id is None:
            return False
        res = (
            db.query(Reservation)
            .filter(
                connector_filter,
                Reservation.id_tag_id == id_tag_id,
                Reservation.status == ReservationStatus.ACTIVE,
            )
            .order_by(Reservation.id.desc())
            .first()
        )
        if res is None:
            return False

    # UPDATE có điều kiện (WHERE status = active) — bảo đảm idempotent
    result = db.execute(
        update(Reservation)
        .where(
            Reservation.id == res.id,
            Reservation.status == ReservationStatus.ACTIVE,
        )
        .values(
            status=ReservationStatus.FULFILLED,
            fulfilled_session_id=session_id,
            fulfilled_at=now,
            cancel_status=CancelStatus.NOT_NEEDED,
        )
    )
    return result.rowcount > 0


# ── S-51: Tài xế huỷ chỗ đã đặt ──────────────────────────────────────────────


class ReservationCancelError(Exception):
    """Lỗi nghiệp vụ khi huỷ đặt chỗ."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def get_charge_point_code_for_connector(
    db: Session, connector_id: int | None
) -> str | None:
    """Tra mã trụ từ connector_id (db PK)."""
    if connector_id is None:
        return None
    from app.models.charge_point import ChargePoint, Connector

    row = (
        db.query(ChargePoint.code)
        .join(Connector, Connector.charge_point_id == ChargePoint.id)
        .filter(Connector.id == connector_id)
        .first()
    )
    return row[0] if row else None


async def cancel_reservation(
    db: Session,
    reservation_id: int,
    user_id: int,
    now: datetime | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Tài xế huỷ chỗ đã đặt (S-51).

    Quy trình:
    1. UPDATE có điều kiện, nguyên tử:
       WHERE id = :id AND driver_user_id = :uid AND status = 'active' AND expiry_at > :cutoff_threshold
       với cutoff_threshold = now + timedelta(seconds=CANCEL_CUTOFF_SECONDS).
       - status = 'cancelled'
       - cancelled_at = :now
       - cancel_status = 'pending'
       - fee_waived_reason = 'driver_cancelled'
    2. Nếu rowcount == 1:
       - Thắng race:
       - Ghi audit log (tài xế, reservation_id, kết quả; không ghi PII).
       - Commit transaction (giải phóng DB write lock trước khi gọi mạng).
       - Tra mã trụ và gửi CancelReservation(reservationId) qua helper T-34 (send_cancel_reservation).
       - Nếu trụ Accepted -> cancel_status = 'done'.
       - Nếu trụ Rejected -> cancel_status = 'gone', ghi cảnh báo.
       - Nếu trụ offline/timeout -> cancel_status = 'pending', để job thử lại xử lý.
       - Trả về thông tin {id, status: 'cancelled', cancelled_at, cancel_status}.
    3. Nếu rowcount == 0:
       - Thua race hoặc không hợp lệ. Đọc lại row để xác định nguyên nhân:
         + Không tồn tại hoặc không thuộc về user_id: 403 Forbidden.
         + res.status == CANCELLED: idempotent, trả 200 dữ liệu hiện có (không gửi lại CancelReservation).
         + res.status == FULFILLED: 409 RESERVATION_FULFILLED.
         + res.status == EXPIRED: 409 RESERVATION_EXPIRED.
         + res.status == ACTIVE nhưng đã quá hạn (now >= expiry_at): 409 RESERVATION_EXPIRED.
         + res.status == ACTIVE nhưng qua cutoff (now >= expiry_at - CANCEL_CUTOFF_SECONDS): 409 CANCEL_TOO_LATE.
    """
    if now is None:
        now = datetime.now(UTC).replace(tzinfo=None)

    cutoff_seconds = settings.CANCEL_CUTOFF_SECONDS
    cutoff_threshold = now + timedelta(seconds=cutoff_seconds)

    # 1. UPDATE có điều kiện, nguyên tử
    result = db.execute(
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.driver_user_id == user_id,
            Reservation.status == ReservationStatus.ACTIVE,
            Reservation.expiry_at > cutoff_threshold,
        )
        .values(
            status=ReservationStatus.CANCELLED,
            cancelled_at=now,
            cancel_status=CancelStatus.PENDING,
            fee_waived_reason="driver_cancelled",
        )
    )

    if result.rowcount == 1:
        # Ghi nhật ký audit
        append_audit(
            db,
            action="reservation.cancelled",
            object_type="reservation",
            object_id=reservation_id,
            actor_id=user_id,
            details={
                "driver_user_id": user_id,
                "cancelled_at": now.isoformat(),
                "cancel_status": CancelStatus.PENDING.value,
                "fee_waived_reason": "driver_cancelled",
                "cancellation_reason": reason,
            },
        )
        # Commit xong mới gửi OCPP (không giữ transaction trong lúc chờ trụ)
        db.commit()

        # Reload row để lấy connector_id
        res = db.get(Reservation, reservation_id)
        cp_code = (
            get_charge_point_code_for_connector(db, res.connector_db_id)
            if res
            else None
        )

        if cp_code:
            await send_cancel_reservation(db, reservation_id, cp_code)

        # Lấy lại trạng thái mới nhất sau khi gửi trụ
        db.expire_all()
        res = db.get(Reservation, reservation_id)
        if res is None:
            raise ReservationCancelError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="not_found",
                detail="Không tìm thấy đặt chỗ",
            )
        return {
            "id": res.id,
            "status": res.status.value,
            "cancelled_at": res.cancelled_at,
            "cancel_status": res.cancel_status.value,
        }

    # rowcount == 0: phân tích nguyên nhân
    db.rollback()
    res = db.get(Reservation, reservation_id)

    # Thống nhất 403 Forbidden khi không tồn tại hoặc không thuộc về người gọi
    if res is None or res.driver_user_id != user_id:
        logger.warning(
            "reservation_cancel_denied: user_id=%s reservation_id=%s",
            user_id,
            reservation_id,
        )
        raise ReservationCancelError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            detail="Không có quyền truy cập đặt chỗ này",
        )

    # Idempotent: đã huỷ bởi chính tài xế đó
    if res.status == ReservationStatus.CANCELLED:
        return {
            "id": res.id,
            "status": res.status.value,
            "cancelled_at": res.cancelled_at,
            "cancel_status": res.cancel_status.value,
        }

    if res.status == ReservationStatus.FULFILLED:
        raise ReservationCancelError(
            status_code=status.HTTP_409_CONFLICT,
            code="RESERVATION_FULFILLED",
            detail="Đặt chỗ đã được sử dụng để sạc",
        )

    if res.status == ReservationStatus.EXPIRED:
        raise ReservationCancelError(
            status_code=status.HTTP_409_CONFLICT,
            code="RESERVATION_EXPIRED",
            detail="Đặt chỗ đã quá hạn và bị tính phí",
        )

    if res.status == ReservationStatus.ACTIVE:
        exp = res.expiry_at
        if hasattr(exp, "tzinfo") and exp.tzinfo is not None:
            exp = exp.astimezone(UTC).replace(tzinfo=None)

        if now >= exp:
            raise ReservationCancelError(
                status_code=status.HTTP_409_CONFLICT,
                code="RESERVATION_EXPIRED",
                detail="Đặt chỗ đã quá hạn",
            )
        else:
            raise ReservationCancelError(
                status_code=status.HTTP_409_CONFLICT,
                code="CANCEL_TOO_LATE",
                detail="Đã qua thời hạn cho phép huỷ đặt chỗ",
            )

    raise ReservationCancelError(
        status_code=status.HTTP_409_CONFLICT,
        code="conflict",
        detail=f"Không thể huỷ đặt chỗ ở trạng thái {res.status.value}",
    )
