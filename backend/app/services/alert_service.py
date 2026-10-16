"""
Service: Quản lý cảnh báo giám sát vận hành (Operational Alerts).
Tham chiếu: SCRUM-90 / S-46 — Cảnh báo khi trụ ngoại tuyến quá lâu hoặc báo lỗi liên tục.
Quy tắc: Idempotency (chống trùng lặp), ghi log cảnh báo và hỗ trợ tự động/thủ công đóng cảnh báo.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert
from app.models.charge_point import ChargePoint, Connector
from app.models.connector_error import ConnectorError
from app.services.audit import ghi_nhat_ky

logger = logging.getLogger(__name__)


def _utc_now(now: datetime | None = None) -> datetime:
    """Trả về mốc thời gian UTC (naive để khớp chuẩn SQLite/Postgres của repo)."""
    if now is not None:
        if now.tzinfo is not None:
            return now.astimezone(UTC).replace(tzinfo=None)
        return now
    return datetime.now(UTC).replace(tzinfo=None)


def notify_alert_dispatch(alert: Alert, charge_point_code: str) -> None:
    """
    Kênh gửi thông báo cảnh báo (Email / Webhook / Notification).
    Trong môi trường thử nghiệm và sandbox, ghi log chuẩn bị sẵn sàng cho email server.
    """
    logger.warning(
        "[ALERT DISPATCH - EMAIL/SMS] Loại: %s | Trụ: %s | Trạng thái: %s | Nội dung: %s",
        alert.alert_type,
        charge_point_code,
        alert.severity,
        alert.message,
    )


def scan_offline_charge_points(db: Session, now: datetime | None = None) -> list[Alert]:
    """
    AC1: Quét các trụ sạc ngoại tuyến quá ngưỡng cấu hình (ALERT_OFFLINE_THRESHOLD_MINUTES).
    AC3: Chống trùng lặp (Idempotent) — Nếu cùng trụ đã có cảnh báo offline 'active', không tạo thêm.
    """
    current_time = _utc_now(now)
    threshold_minutes = settings.ALERT_OFFLINE_THRESHOLD_MINUTES
    cutoff = current_time - timedelta(minutes=threshold_minutes)

    # Lấy các trụ sạc đang offline hoặc mất liên lạc quá thời gian ngưỡng
    charge_points = db.query(ChargePoint).all()
    created_alerts: list[Alert] = []

    for cp in charge_points:
        is_offline = False
        last_contact = cp.last_seen_at

        if cp.status == "offline":
            # Nếu đang offline và (không có mốc liên lạc hoặc mốc liên lạc quá hạn)
            if last_contact is None or last_contact <= cutoff:
                is_offline = True
        else:
            # Dù status ghi online nhưng quá hạn liên lạc
            if last_contact is not None and last_contact <= cutoff or last_contact is None and cp.created_at <= cutoff:
                is_offline = True

        if is_offline:
            # Kiểm tra chống trùng cảnh báo
            existing = (
                db.query(Alert)
                .filter(
                    Alert.charge_point_id == cp.id,
                    Alert.alert_type == "offline",
                    Alert.status == "active",
                )
                .first()
            )
            if existing is not None:
                # Đã có cảnh báo đang kích hoạt -> Không tạo thêm
                continue

            last_seen_str = (
                last_contact.strftime("%Y-%m-%d %H:%M:%S")
                if last_contact
                else "chưa từng liên lạc"
            )
            msg = (
                f"Trụ sạc {cp.code} ngoại tuyến quá {threshold_minutes} phút. "
                f"Lần liên lạc cuối: {last_seen_str}."
            )

            alert = Alert(
                charge_point_id=cp.id,
                connector_id=None,
                alert_type="offline",
                severity="critical",
                status="active",
                message=msg,
                error_count=None,
                triggered_at=current_time,
            )
            db.add(alert)
            created_alerts.append(alert)
            notify_alert_dispatch(alert, cp.code)

    if created_alerts:
        db.flush()

    return created_alerts


def scan_connector_errors(db: Session, now: datetime | None = None) -> list[Alert]:
    """
    AC2: Quét các đầu nối gặp >= ALERT_ERROR_COUNT_THRESHOLD lỗi trong ALERT_ERROR_WINDOW_MINUTES phút.
    AC3: Chống trùng lặp — Nếu đầu nối đã có cảnh báo connector_error 'active', không tạo thêm.
    """
    current_time = _utc_now(now)
    window_minutes = settings.ALERT_ERROR_WINDOW_MINUTES
    threshold_count = settings.ALERT_ERROR_COUNT_THRESHOLD
    cutoff = current_time - timedelta(minutes=window_minutes)

    # Đếm số lỗi cho từng đầu nối trong khoảng thời gian cửa sổ
    rows = (
        db.query(
            ConnectorError.connector_id,
            func.count(ConnectorError.id).label("err_cnt"),
        )
        .filter(ConnectorError.occurred_at >= cutoff)
        .group_by(ConnectorError.connector_id)
        .having(func.count(ConnectorError.id) >= threshold_count)
        .all()
    )

    created_alerts: list[Alert] = []

    for connector_id, count in rows:
        connector = (
            db.query(Connector)
            .filter(Connector.id == connector_id)
            .first()
        )
        if not connector:
            continue

        cp = db.query(ChargePoint).filter(ChargePoint.id == connector.charge_point_id).first()
        cp_code = cp.code if cp else f"CP#{connector.charge_point_id}"

        # Kiểm tra chống trùng
        existing = (
            db.query(Alert)
            .filter(
                Alert.charge_point_id == connector.charge_point_id,
                Alert.connector_id == connector.id,
                Alert.alert_type == "connector_error",
                Alert.status == "active",
            )
            .first()
        )
        if existing is not None:
            continue

        msg = (
            f"Đầu nối {connector.connector_id} của trụ {cp_code} ghi nhận "
            f"{count} lỗi liên tiếp trong {window_minutes} phút gần đây."
        )

        alert = Alert(
            charge_point_id=connector.charge_point_id,
            connector_id=connector.id,
            alert_type="connector_error",
            severity="warning",
            status="active",
            message=msg,
            error_count=count,
            triggered_at=current_time,
        )
        db.add(alert)
        created_alerts.append(alert)
        notify_alert_dispatch(alert, cp_code)

    if created_alerts:
        db.flush()

    return created_alerts


def scan_all_alerts(db: Session, now: datetime | None = None) -> list[Alert]:
    """Chạy đồng thời cả 2 quét cảnh báo và commit kết quả vào DB."""
    current_time = _utc_now(now)
    offline_alerts = scan_offline_charge_points(db, now=current_time)
    error_alerts = scan_connector_errors(db, now=current_time)

    all_created = offline_alerts + error_alerts
    if all_created:
        db.commit()
        for alert in all_created:
            db.refresh(alert)
    return all_created


def resolve_alert(
    db: Session,
    alert_id: int,
    resolved_by_id: int | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Alert:
    """
    AC5: Đóng cảnh báo (thủ công bởi vận hành viên hoặc quản trị viên).
    Idempotent: Nếu đã đóng rồi thì trả về nguyên trạng.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise ValueError(f"Không tìm thấy cảnh báo với ID {alert_id}")

    if alert.status == "resolved":
        return alert

    current_time = _utc_now(now)
    alert.status = "resolved"
    alert.resolved_at = current_time
    alert.resolved_by_id = resolved_by_id

    if note:
        alert.message = f"{alert.message} [Ghi chú giải quyết: {note.strip()}]"

    # Ghi nhận vào audit log (sổ nhật ký thao tác)
    ghi_nhat_ky(
        db,
        action="alert.resolve",
        object_type="alert",
        object_id=alert.id,
        actor_id=resolved_by_id,
        details={
            "alert_type": alert.alert_type,
            "charge_point_id": alert.charge_point_id,
            "connector_id": alert.connector_id,
            "note": note,
        },
    )

    db.commit()
    db.refresh(alert)
    logger.info("Cảnh báo ID %d đã được đóng bởi User ID %s", alert.id, resolved_by_id)
    return alert


def auto_resolve_recovered_offline_alerts(
    db: Session, now: datetime | None = None
) -> list[Alert]:
    """
    Tự động đóng các cảnh báo offline khi trụ sạc đã trực tuyến trở lại và gửi tin nhắn.
    """
    current_time = _utc_now(now)
    active_offline_alerts = (
        db.query(Alert)
        .filter(Alert.alert_type == "offline", Alert.status == "active")
        .all()
    )

    resolved: list[Alert] = []
    for alert in active_offline_alerts:
        cp = db.query(ChargePoint).filter(ChargePoint.id == alert.charge_point_id).first()
        if cp and cp.status == "online":
            alert.status = "resolved"
            alert.resolved_at = current_time
            alert.message = f"{alert.message} (Tự động đóng: Trụ đã trực tuyến trở lại)."
            resolved.append(alert)

    if resolved:
        db.commit()
        for a in resolved:
            db.refresh(a)
    return resolved


def get_alerts(
    db: Session,
    status: str | None = None,
    alert_type: str | None = None,
    charge_point_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Alert], int]:
    """
    Truy vấn danh sách cảnh báo có phân trang và bộ lọc.
    Trả về (items, total_count).
    """
    query = db.query(Alert)

    if status:
        query = query.filter(Alert.status == status)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if charge_point_id:
        query = query.filter(Alert.charge_point_id == charge_point_id)

    total = query.count()
    items = (
        query.order_by(Alert.triggered_at.desc(), Alert.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total
