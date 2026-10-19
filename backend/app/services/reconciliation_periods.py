"""Create and enforce immutable snapshots for financial reconciliation periods."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.reconciliation_period_lock import ReconciliationPeriodLock
from app.models.station import Station
from app.models.station_tariff import StationTariff
from app.services.audit import append_audit
from app.services.financial_reconciliation import (
    filter_financial_reconciliation_report,
    get_financial_reconciliation_report,
)
from app.services.financial_reconciliation_pricing import station_timezone


class FinancialPeriodLocked(ValueError):
    """Raised when an OCPP/billing write targets a locked local session date."""


def find_period_lock(
    db: Session, station_id: int, from_date: date, to_date: date
) -> ReconciliationPeriodLock | None:
    return (
        db.query(ReconciliationPeriodLock)
        .filter_by(station_id=station_id, from_date=from_date, to_date=to_date)
        .first()
    )


def get_locked_period_report(
    lock: ReconciliationPeriodLock,
    status: str = "all",
    charge_point_code: str | None = None,
) -> dict:
    report = filter_financial_reconciliation_report(
        lock.snapshot, status, charge_point_code
    )
    return {
        **report,
        "period_state": "locked",
        "locked_at": lock.locked_at.isoformat() + "Z",
        "locked_by": lock.locked_by_id,
    }


def _timezone_for_station(db: Session, station_id: int, at: datetime) -> str:
    tariffs = (
        db.query(StationTariff)
        .filter(StationTariff.station_id == station_id)
        .order_by(StationTariff.effective_from, StationTariff.id)
        .all()
    )
    return station_timezone(tariffs, at)


def _local_date(at: datetime, timezone_name: str) -> date:
    instant = at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)
    return instant.astimezone(ZoneInfo(timezone_name)).date()


def ensure_station_period_open(
    db: Session,
    station_id: int | None,
    session_started_at: datetime,
    event_at: datetime | None,
    session_id: int | None = None,
) -> None:
    if station_id is None or event_at is None:
        return
    # Reconciliation close and OCPP session writes use this station row as a
    # transaction-level mutex so a late stop cannot race the saved snapshot.
    db.query(Station.id).filter(Station.id == station_id).with_for_update().first()
    locks = (
        db.query(ReconciliationPeriodLock)
        .filter(ReconciliationPeriodLock.station_id == station_id)
        .all()
    )
    if not locks:
        return
    timezone_name = _timezone_for_station(db, station_id, session_started_at)
    local_day = _local_date(event_at, timezone_name)
    if any(lock.from_date <= local_day <= lock.to_date for lock in locks):
        session_label = f" {session_id}" if session_id is not None else ""
        raise FinancialPeriodLocked(
            f"Phiên{session_label} thuộc kỳ {local_day.isoformat()} đã khóa; "
            "không thể ghi phiên, hóa đơn hoặc bút toán mới."
        )


def ensure_session_period_open(
    db: Session,
    session: ChargingSession,
    ended_at: datetime | None = None,
) -> None:
    ensure_station_period_open(
        db,
        session.station_id,
        session.started_at,
        ended_at or session.ended_at,
        session.id,
    )


def _assert_no_open_or_unreviewed_sessions(
    db: Session,
    station_id: int,
    from_date: date,
    to_date: date,
    timezone_name: str,
) -> None:
    zone = ZoneInfo(timezone_name)
    local_start = datetime.combine(from_date, time.min, tzinfo=zone)
    local_end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=zone)
    utc_start = local_start.astimezone(UTC).replace(tzinfo=None)
    utc_end = local_end.astimezone(UTC).replace(tzinfo=None)
    open_session = (
        db.query(ChargingSession.id)
        .filter(
            ChargingSession.station_id == station_id,
            ChargingSession.status == "active",
            ChargingSession.ended_at.is_(None),
            ChargingSession.started_at < utc_end,
        )
        .first()
    )
    unresolved = (
        db.query(ChargingSession.id)
        .filter(
            ChargingSession.station_id == station_id,
            ChargingSession.status.in_(("anomaly", "needs_review")),
            or_(
                ChargingSession.started_at >= utc_start,
                ChargingSession.ended_at >= utc_start,
            ),
            or_(
                ChargingSession.started_at < utc_end,
                ChargingSession.ended_at < utc_end,
            ),
        )
        .first()
    )
    if open_session or unresolved:
        raise ValueError("Không thể chốt kỳ khi còn phiên đang mở hoặc bất thường chưa xử lý")


def close_financial_reconciliation_period(
    db: Session,
    *,
    station_id: int,
    from_date: date,
    to_date: date,
    actor_id: int,
    actor_email: str,
    actor_name: str,
    station_owner_user_id: int | None = None,
) -> tuple[ReconciliationPeriodLock, bool]:
    """Save one immutable report snapshot; repeated closes return the same lock."""
    station = (
        db.query(Station)
        .filter(Station.id == station_id)
        .with_for_update()
        .first()
    )
    if station is None:
        raise LookupError("Không tìm thấy trạm sạc")
    if station_owner_user_id is not None and station.owner_id != station_owner_user_id:
        raise PermissionError("Bạn chỉ có thể chốt kỳ của trạm mình sở hữu")
    existing = find_period_lock(db, station_id, from_date, to_date)
    if existing is not None:
        return existing, True

    now = datetime.now(UTC).replace(tzinfo=None)
    timezone_name = _timezone_for_station(db, station_id, now)
    local_today = _local_date(now, timezone_name)
    if to_date >= local_today:
        raise ValueError("Chỉ có thể chốt kỳ đã kết thúc")
    _assert_no_open_or_unreviewed_sessions(
        db, station_id, from_date, to_date, timezone_name
    )
    snapshot = get_financial_reconciliation_report(
        db,
        from_date=from_date,
        to_date=to_date,
        station_id=station_id,
    )
    snapshot["filters"]["stations"] = [{"id": station.id, "name": station.name}]
    snapshot["filters"]["charge_points"] = [
        {"code": point.code, "station_id": point.station_id}
        for point in db.query(ChargePoint)
        .filter(ChargePoint.station_id == station_id)
        .order_by(ChargePoint.code)
        .all()
    ]
    if snapshot["summary"]["review_count"]:
        raise ValueError("Hãy xử lý toàn bộ phiên cần xem xét trước khi chốt kỳ")
    snapshot.update({
        "period_state": "locked",
        "locked_at": now.isoformat() + "Z",
        "locked_by": actor_id,
    })
    lock = ReconciliationPeriodLock(
        station_id=station_id,
        from_date=from_date,
        to_date=to_date,
        status="locked",
        snapshot=snapshot,
        locked_by_id=actor_id,
        locked_at=now,
    )
    db.add(lock)
    try:
        db.flush()
        append_audit(
            db,
            action="reconciliation.period_locked",
            object_type="reconciliation_period_lock",
            object_id=lock.id,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            details={
                "station_id": station_id,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "total_kwh": snapshot["summary"]["total_kwh"],
                "total_collected_vnd": snapshot["summary"]["total_collected_vnd"],
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = find_period_lock(db, station_id, from_date, to_date)
        if existing is None:
            raise
        return existing, True
    except Exception:
        db.rollback()
        raise
    db.refresh(lock)
    return lock, False
