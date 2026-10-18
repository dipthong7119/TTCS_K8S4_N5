"""
Router: alerts
Tham chiếu: SCRUM-90 / S-46 — Cảnh báo khi trụ ngoại tuyến quá lâu hoặc báo lỗi liên tục.
Phân quyền: deny-by-default, chỉ admin và operator được truy cập.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_role
from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertListResponse, AlertResolveRequest, AlertResponse
from app.services.alert_service import (
    get_alerts,
    resolve_alert,
    scan_all_alerts,
)

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
    dependencies=[Depends(require_role("operator", "admin"))],
)


def _to_alert_response(alert: Alert) -> AlertResponse:
    code = None
    if alert.charge_point:
        code = alert.charge_point.code
    station_name = alert.charge_point.station.name if alert.charge_point and alert.charge_point.station else None
    error_code = alert.connector.error_code if alert.connector else None
    return AlertResponse(
        id=alert.id,
        charge_point_id=alert.charge_point_id,
        charge_point_code=code,
        station_name=station_name,
        connector_id=alert.connector_id,
        error_code=error_code,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status=alert.status,
        message=alert.message,
        error_count=alert.error_count,
        triggered_at=alert.triggered_at,
        resolved_at=alert.resolved_at,
        resolved_by_id=alert.resolved_by_id,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


@router.get("", response_model=AlertListResponse)
def list_alerts(
    status_filter: str | None = Query(
        None, alias="status", description="Lọc theo trạng thái: active | resolved"
    ),
    alert_type: str | None = Query(None, description="Lọc theo loại: offline | connector_error"),
    charge_point_id: int | None = Query(None, description="Lọc theo ID trụ sạc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách các cảnh báo giám sát vận hành (AC1, AC2, AC4).
    Hỗ trợ phân trang và lọc theo trạng thái/loại cảnh báo/trụ sạc.
    """
    items, total = get_alerts(
        db,
        status=status_filter,
        alert_type=alert_type,
        charge_point_id=charge_point_id,
        skip=skip,
        limit=limit,
    )

    active_count = db.query(Alert).filter(Alert.status == "active").count()
    response_items = [_to_alert_response(a) for a in items]
    return AlertListResponse(total=total, items=response_items, active_count=active_count)


@router.get("/summary")
def get_alerts_summary(db: Session = Depends(get_db)):
    """
    AC4: Thống kê nhanh số cảnh báo active để hiển thị badge/thanh thông báo ở đầu màn hình giám sát.
    """
    active_offline = (
        db.query(Alert)
        .filter(Alert.alert_type == "offline", Alert.status == "active")
        .count()
    )
    active_error = (
        db.query(Alert)
        .filter(Alert.alert_type == "connector_error", Alert.status == "active")
        .count()
    )
    return {
        "active_total": active_offline + active_error,
        "active_offline": active_offline,
        "active_connector_error": active_error,
    }


@router.post("/scan", response_model=list[AlertResponse])
def trigger_alert_scan(db: Session = Depends(get_db)):
    """
    Kích hoạt quét phát hiện sự cố theo yêu cầu (on-demand scan).
    Chạy kiểm tra trụ offline và lỗi đầu nối, sinh cảnh báo mới nếu có.
    """
    new_alerts = scan_all_alerts(db)
    return [_to_alert_response(a) for a in new_alerts]


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_existing_alert(
    alert_id: int,
    body: AlertResolveRequest | None = None,
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """
    AC5: Vận hành viên hoặc quản trị viên xác nhận và đóng cảnh báo.
    Ghi nhận người đóng, thời điểm đóng và cập nhật sổ nhật ký thao tác audit_logs.
    """
    note = body.note if body else None
    actor_id = current_user.id if current_user else None

    try:
        resolved = resolve_alert(db, alert_id=alert_id, resolved_by_id=actor_id, note=note)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return _to_alert_response(resolved)
