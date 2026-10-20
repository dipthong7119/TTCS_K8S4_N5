"""
Router: privacy
Tham chiếu: SCRUM-92 / S-57 — Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển (Nghị định 13/2023/NĐ-CP).
Phân quyền:
- Tài xế: gửi yêu cầu và tra cứu yêu cầu của chính mình.
- Quản trị viên/Vận hành (admin, operator): tra cứu danh sách yêu cầu.
- Quản trị viên (admin): phê duyệt hoặc từ chối yêu cầu.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_role
from app.core.security import verify_password
from app.database import get_db
from app.models.charging_session import ChargingSession
from app.models.data_erasure import DataErasureRequest
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.schemas.data_erasure import (
    DataErasureCreateRequest,
    DataErasureListResponse,
    DataErasureRejectRequest,
    DataErasureResponse,
    PrivacyDeletionCreateRequest,
    PrivacyDeletionRejectRequest,
)
from app.services.privacy_service import (
    approve_erasure_request,
    cancel_erasure_request,
    create_erasure_request,
    get_my_erasure_requests,
    hide_erasure_request,
    list_erasure_requests,
    reject_erasure_request,
    to_erasure_response,
)
from app.services.wallet import wallet_totals

router = APIRouter(
    prefix="/privacy",
    tags=["Privacy & Data Erasure"],
)


def _to_page_request(db: Session, req: DataErasureRequest) -> dict:
    """Expose the field names consumed by the existing privacy page."""
    driver = req.user
    active_sessions = 0
    active_reservations = 0
    balance_vnd = 0
    if driver:
        balance_vnd = wallet_totals(db, driver.id)["balance_vnd"]
        active_sessions = (
            db.query(func.count(ChargingSession.id))
            .filter(
                ChargingSession.user_id == driver.id,
                ChargingSession.status == "active",
            )
            .scalar()
            or 0
        )
        active_reservations = (
            db.query(func.count(Reservation.id))
            .filter(
                Reservation.user_id == driver.id,
                Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.ACTIVE]),
            )
            .scalar()
            or 0
        )
    return {
        "id": req.id,
        "user_id": req.user_id,
        "driver_name": driver.full_name if driver else None,
        "driver_email": driver.email if driver else None,
        "driver_phone": getattr(driver, "phone", None) if driver else None,
        "plate_number": getattr(driver, "plate_number", None) if driver else None,
        "reason": req.request_reason,
        "reason_label": req.request_reason_label or req.request_reason,
        "reason_detail": req.request_reason_detail,
        "request_reason": req.request_reason,
        "rejection_reason": req.rejection_reason,
        "reject_reason": req.rejection_reason,
        "status": req.status,
        "resolution_action": req.resolution_action,
        "balance_vnd": balance_vnd,
        "active_sessions_count": active_sessions,
        "active_reservations_count": active_reservations,
        "requested_at": req.requested_at,
        "created_at": req.created_at,
        "processed_at": req.processed_at,
        "processed_by": req.processed_by,
        "updated_at": req.updated_at,
    }


@router.get(
    "/profile",
    dependencies=[Depends(require_role("driver"))],
)
def get_privacy_profile(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Return the driver's profile and privacy-request state for the existing page."""
    driver = db.query(User).filter(User.id == current_user.id).first() or current_user
    active_request = (
        db.query(DataErasureRequest)
        .filter(
            DataErasureRequest.user_id == driver.id,
            DataErasureRequest.status == "pending",
        )
        .order_by(DataErasureRequest.requested_at.desc())
        .first()
    )
    sessions_count = (
        db.query(func.count(ChargingSession.id))
        .filter(ChargingSession.user_id == driver.id)
        .scalar()
        or 0
    )
    return {
        "display_name": driver.full_name,
        "email": driver.email,
        "phone": getattr(driver, "phone", None),
        "plate_number": getattr(driver, "plate_number", None),
        "charging_sessions_count": sessions_count,
        "balance_vnd": wallet_totals(db, driver.id)["balance_vnd"],
        "active_request": (
            _to_page_request(db, active_request) if active_request else None
        ),
    }


@router.post(
    "/deletion-requests",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("driver"))],
)
def submit_page_deletion_request(
    payload: PrivacyDeletionCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Accept the existing page's payload and require password confirmation."""
    driver = db.query(User).filter(User.id == current_user.id).first() or current_user
    if not verify_password(payload.password, driver.password_hash):
        raise HTTPException(
            status_code=400, detail="Mật khẩu xác nhận không chính xác."
        )
    req = create_erasure_request(
        db,
        driver,
        payload.reason,
        reason_label=payload.reason_label,
        reason_detail=payload.reason_detail,
    )
    return _to_page_request(db, req)


@router.post(
    "/deletion-requests/{request_id}/cancel",
    dependencies=[Depends(require_role("driver"))],
)
def cancel_page_deletion_request(
    request_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    driver = db.query(User).filter(User.id == current_user.id).first() or current_user
    return _to_page_request(db, cancel_erasure_request(db, request_id, driver))


@router.get(
    "/admin/deletion-requests",
    dependencies=[Depends(require_role("admin", "operator"))],
)
def list_page_deletion_requests(
    status_filter: str | None = Query(None, alias="status"),
    driver_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = list_erasure_requests(
        db, status=status_filter, driver_id=driver_id, skip=skip, limit=limit
    )
    return {
        "items": [_to_page_request(db, item) for item in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post(
    "/admin/deletion-requests/{request_id}/approve",
    dependencies=[Depends(require_role("admin"))],
)
def approve_page_deletion_request(
    request_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    admin_user = (
        db.query(User).filter(User.id == current_user.id).first() or current_user
    )
    req = approve_erasure_request(db, request_id, admin_user)
    return _to_page_request(db, req)


@router.post(
    "/admin/deletion-requests/{request_id}/hide",
    dependencies=[Depends(require_role("admin"))],
)
def hide_page_deletion_request(
    request_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    admin_user = db.query(User).filter(User.id == current_user.id).first() or current_user
    req = hide_erasure_request(db, request_id, admin_user)
    return _to_page_request(db, req)


@router.post(
    "/admin/deletion-requests/{request_id}/reject",
    dependencies=[Depends(require_role("admin"))],
)
def reject_page_deletion_request(
    request_id: int,
    payload: PrivacyDeletionRejectRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    admin_user = (
        db.query(User).filter(User.id == current_user.id).first() or current_user
    )
    req = reject_erasure_request(db, request_id, admin_user, payload.reason)
    return _to_page_request(db, req)


@router.post(
    "/erasure-requests",
    response_model=DataErasureResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("driver"))],
)
def submit_erasure_request(
    payload: DataErasureCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Tài xế gửi yêu cầu xóa dữ liệu cá nhân và lịch sử di chuyển (SCRUM-92 / S-57)."""
    driver = db.query(User).filter(User.id == current_user.id).first()
    if not driver:
        driver = current_user
    req = create_erasure_request(db, driver, payload.reason)
    return to_erasure_response(req)


@router.get(
    "/erasure-requests/my",
    response_model=list[DataErasureResponse],
    dependencies=[Depends(require_role("driver"))],
)
def get_my_requests(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Tài xế tra cứu danh sách yêu cầu của bản thân."""
    requests = get_my_erasure_requests(db, current_user.id)
    return [to_erasure_response(r) for r in requests]


@router.get(
    "/admin/erasure-requests",
    response_model=DataErasureListResponse,
    dependencies=[Depends(require_role("admin", "operator"))],
)
def list_all_erasure_requests(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Lọc theo trạng thái: pending | approved | rejected",
    ),
    driver_id: int | None = Query(None, description="Lọc theo ID tài xế"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Quản trị viên và người vận hành tra cứu danh sách các yêu cầu xóa dữ liệu."""
    items, total = list_erasure_requests(
        db, status=status_filter, driver_id=driver_id, skip=skip, limit=limit
    )
    return DataErasureListResponse(
        items=[to_erasure_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/admin/erasure-requests/{request_id}/approve",
    response_model=DataErasureResponse,
    dependencies=[Depends(require_role("admin"))],
)
def approve_request(
    request_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Quản trị viên phê duyệt và thực hiện ẩn danh hóa dữ liệu cá nhân."""
    admin_user = db.query(User).filter(User.id == current_user.id).first()
    if not admin_user:
        admin_user = current_user
    req = approve_erasure_request(db, request_id, admin_user)
    return to_erasure_response(req)


@router.post(
    "/admin/erasure-requests/{request_id}/reject",
    response_model=DataErasureResponse,
    dependencies=[Depends(require_role("admin"))],
)
def reject_request(
    request_id: int,
    payload: DataErasureRejectRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Quản trị viên từ chối yêu cầu xóa dữ liệu."""
    admin_user = db.query(User).filter(User.id == current_user.id).first()
    if not admin_user:
        admin_user = current_user
    req = reject_erasure_request(
        db, request_id, admin_user, payload.rejection_reason
    )
    return to_erasure_response(req)
