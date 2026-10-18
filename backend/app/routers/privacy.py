"""
Router: privacy
Tham chiếu: SCRUM-92 / S-57 — Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển (Nghị định 13/2023/NĐ-CP).
Phân quyền:
- Tài xế: gửi yêu cầu và tra cứu yêu cầu của chính mình.
- Quản trị viên/Vận hành (admin, operator): tra cứu danh sách yêu cầu.
- Quản trị viên (admin): phê duyệt hoặc từ chối yêu cầu.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.data_erasure import (
    DataErasureCreateRequest,
    DataErasureListResponse,
    DataErasureRejectRequest,
    DataErasureResponse,
)
from app.services.privacy_service import (
    approve_erasure_request,
    create_erasure_request,
    get_my_erasure_requests,
    list_erasure_requests,
    reject_erasure_request,
    to_erasure_response,
)

router = APIRouter(
    prefix="/privacy",
    tags=["Privacy & Data Erasure"],
)


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
