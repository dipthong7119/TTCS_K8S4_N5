"""Read-only, paginated audit history for administrators and operators."""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(deny_unannotated_route)],
)


@router.get("", dependencies=[Depends(require_role("admin", "operator"))])
async def list_audit_logs(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=50),
    charge_point_code: str | None = Query(None, max_length=50),
    actor: str | None = Query(None, max_length=255),
    driver_id: int | None = Query(None, description="Lọc theo ID tài xế (SCRUM-91)"),
    driver: str | None = Query(
        None, max_length=255, description="Lọc theo tên hoặc email tài xế (SCRUM-91)"
    ),
    action: str | None = Query(None, max_length=100, description="Lọc theo loại hành động (SCRUM-91)"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    query = db.query(AuditLog)
    if charge_point_code:
        query = query.filter(AuditLog.charge_point_code.ilike(f"%{charge_point_code.strip()}%"))
    if actor:
        search = f"%{actor.strip()}%"
        query = query.filter(or_(AuditLog.actor_email.ilike(search), AuditLog.actor_name.ilike(search)))
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if driver_id is not None:
        query = query.filter(
            or_(
                AuditLog.target_user_id == driver_id,
                AuditLog.object_id == str(driver_id),
            )
        )
    if driver:
        driver_search = f"%{driver.strip()}%"
        matched_user_ids = [
            u.id
            for u in db.query(User.id)
            .filter(
                or_(
                    User.email.ilike(driver_search),
                    User.full_name.ilike(driver_search),
                )
            )
            .all()
        ]
        conds = []
        if matched_user_ids:
            conds.append(AuditLog.target_user_id.in_(matched_user_ids))
            conds.append(AuditLog.object_id.in_([str(uid) for uid in matched_user_ids]))
        if conds:
            query = query.filter(or_(*conds))
        else:
            query = query.filter(AuditLog.id == -1)

    if date_from:
        query = query.filter(
            AuditLog.created_at >= datetime.combine(date_from, time.min)
        )
    if date_to:
        query = query.filter(
            AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min)
        )

    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": entry.id,
                "actor_id": entry.actor_id,
                "actor_email": entry.actor_email,
                "actor_name": entry.actor_name,
                "target_user_id": entry.target_user_id,
                "action": entry.action,
                "object_type": entry.object_type,
                "object_id": entry.object_id,
                "charge_point_code": entry.charge_point_code,
                "details": entry.details,
                "created_at": entry.created_at.isoformat() + "Z",
            }
            for entry in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.api_route(
    "/{audit_id}",
    methods=["PUT", "PATCH", "DELETE"],
    dependencies=[Depends(require_role("admin", "operator"))],
)
async def reject_audit_mutation(audit_id: int):
    raise HTTPException(status_code=405, detail="Nhật ký kiểm toán chỉ được đọc")
