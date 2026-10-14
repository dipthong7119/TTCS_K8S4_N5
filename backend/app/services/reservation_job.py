"""Job nền xử lý đặt chỗ quá hạn (S-52).

Theo mẫu các job hiện có (T-26, T-31) trong services/jobs.py:
- Hàm _once() chạy đồng bộ, dễ test.
- Hàm async wrapper vòng lặp chờ theo chu kỳ.
- Chạy ngay một lần khi khởi động (bù các chỗ quá hạn khi tiến trình tắt).
- Lỗi ở một đặt chỗ không chặn các đặt chỗ khác.
- Chạy khi không có gì thì không ghi log.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.charge_point import ChargePoint, Connector
from app.models.reservation import CancelStatus, Reservation, ReservationStatus
from app.services.reservations import expire_reservation, is_overdue, send_cancel_reservation

logger = logging.getLogger(__name__)


# ── Bước 1: quét đặt chỗ active quá hạn ─────────────────────────────────────


def expire_overdue_reservations_once(db: Session, now: datetime | None = None) -> int:
    """Quét tối đa RESERVATION_EXPIRY_BATCH đặt chỗ active đã quá hạn và xử lý.

    Mỗi đặt chỗ được xử lý trong transaction riêng; lỗi ở một cái không chặn cái khác.
    Trả về số đặt chỗ đã chuyển trạng thái thành công.
    """
    if now is None:
        now = datetime.now(UTC).replace(tzinfo=None)

    grace = settings.NO_SHOW_GRACE_SECONDS
    batch = settings.RESERVATION_EXPIRY_BATCH

    # Deadline: expiry_at phải <= now - grace
    # SQLite không có interval function — so sánh timestamp bằng Python
    deadline = now - timedelta(seconds=grace)

    # Truy vấn dùng chỉ mục (status, expiry_at)
    rows = (
        db.query(Reservation.id)
        .filter(
            Reservation.status == ReservationStatus.ACTIVE,
            Reservation.expiry_at <= deadline,
        )
        .limit(batch)
        .all()
    )

    if not rows:
        return 0

    processed = 0
    for (res_id,) in rows:
        try:
            ok = expire_reservation(db, res_id, now)
            if ok:
                processed += 1
        except Exception:
            db.rollback()
            logger.exception(
                "expire_reservation thất bại: reservation=%s", res_id
            )
    return processed


# ── Bước 2: thử lại CancelReservation cho các đặt chỗ expired/pending ────────


async def retry_cancel_reservations_once(
    db: Session, now: datetime | None = None
) -> int:
    """Thử lại CancelReservation cho các đặt chỗ chưa huỷ được.

    Điều kiện:
    - status = expired, cancel_status = pending
    - cancel_attempts < CANCEL_RESERVATION_MAX_ATTEMPTS
    - expired_at + CANCEL_RESERVATION_RETRY_WINDOW > now (còn trong cửa sổ thử lại)
    """
    if now is None:
        now = datetime.now(UTC).replace(tzinfo=None)

    retry_window = timedelta(seconds=settings.CANCEL_RESERVATION_RETRY_WINDOW)
    max_attempts = settings.CANCEL_RESERVATION_MAX_ATTEMPTS
    cutoff = now - retry_window  # expired_at phải sau cutoff để còn được thử

    # Tìm các đặt chỗ cần thử lại
    rows = (
        db.query(Reservation.id, Reservation.connector_id, Reservation.cancel_attempts, Reservation.expired_at)
        .filter(
            Reservation.status == ReservationStatus.EXPIRED,
            Reservation.cancel_status == CancelStatus.PENDING,
            Reservation.cancel_attempts < max_attempts,
            Reservation.expired_at >= cutoff,
        )
        .limit(settings.RESERVATION_EXPIRY_BATCH)
        .all()
    )

    if not rows:
        return 0

    sent = 0
    for res_id, connector_id, attempts, _ in rows:
        # Tra kết nối sống theo mã trụ
        cp_code = _get_charge_point_code(db, connector_id)
        if cp_code is None:
            continue
        try:
            await send_cancel_reservation(db, res_id, cp_code)
            sent += 1
        except Exception:
            db.rollback()
            logger.exception(
                "retry CancelReservation thất bại: reservation=%s cp=%s",
                res_id,
                cp_code,
            )

    # Đánh abandoned cho những đặt chỗ hết số lần hoặc hết cửa sổ thời gian
    _abandon_stale_cancels(db, now, max_attempts, cutoff)

    return sent


def _abandon_stale_cancels(
    db: Session,
    now: datetime,
    max_attempts: int,
    cutoff: datetime,
) -> None:
    """Chuyển cancel_status → abandoned khi hết số lần hoặc hết thời gian."""
    db.execute(
        update(Reservation)
        .where(
            Reservation.status == ReservationStatus.EXPIRED,
            Reservation.cancel_status == CancelStatus.PENDING,
            (Reservation.cancel_attempts >= max_attempts)
            | (Reservation.expired_at < cutoff),
        )
        .values(cancel_status=CancelStatus.ABANDONED)
    )
    db.commit()


def _get_charge_point_code(db: Session, connector_id: int) -> str | None:
    """Tra mã trụ từ connector_id (db PK)."""
    row = (
        db.query(ChargePoint.code)
        .join(Connector, Connector.charge_point_id == ChargePoint.id)
        .filter(Connector.id == connector_id)
        .first()
    )
    return row[0] if row else None


# ── Job vòng lặp chính ────────────────────────────────────────────────────────


async def check_expired_reservations() -> None:
    """Job nền chạy chu kỳ RESERVATION_EXPIRY_JOB_INTERVAL giây.

    Chạy ngay khi khởi động (bù các chỗ quá hạn trong lúc tiến trình tắt),
    sau đó chờ theo chu kỳ.

    Theo đúng mẫu check_offline_charge_points() trong services/jobs.py.
    """
    while True:
        try:
            with SessionLocal() as db:
                # Bước 1: xử lý active → expired (đồng bộ)
                n_expired = expire_overdue_reservations_once(db)
                if n_expired:
                    logger.info("reservation.expired_batch: count=%s", n_expired)

            with SessionLocal() as db:
                # Bước 2: thử lại CancelReservation (async, không giữ transaction)
                n_sent = await retry_cancel_reservations_once(db)
                if n_sent:
                    logger.info("reservation.cancel_retried: count=%s", n_sent)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reservation expiry job thất bại")

        await asyncio.sleep(settings.RESERVATION_EXPIRY_JOB_INTERVAL)
