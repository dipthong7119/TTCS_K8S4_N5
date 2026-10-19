"""SCRUM-85 financial reconciliation API for accounting reports."""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.station import Station
from app.schemas.reconciliation import ReconciliationPeriodLockRequest
from app.services.financial_reconciliation import get_financial_reconciliation_report
from app.services.reconciliation_periods import (
    close_financial_reconciliation_period,
    find_period_lock,
    get_locked_period_report,
)

router = APIRouter(
    prefix="/reconciliation",
    tags=["financial reconciliation"],
    dependencies=[Depends(deny_unannotated_route)],
)


@router.get(
    "/financial",
    dependencies=[Depends(require_role("admin", "accountant", "station_owner"))],
)
def get_financial_reconciliation(
    current_user: CurrentUser,
    from_date: date = Query(...),
    to_date: date = Query(...),
    station_id: int | None = Query(None, gt=0),
    charge_point_code: str | None = Query(None, min_length=1),
    status: Literal[
        "all",
        "review",
        "missing_invoice",
        "missing_ledger",
        "amount_mismatch",
        "collection_mismatch",
        "missing_pricing",
    ] = Query("all"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reconcile completed-session energy, tariff invoices, and wallet charges."""
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="Ngày bắt đầu phải trước hoặc bằng ngày kết thúc",
        )
    roles = {role.name for role in current_user.roles}
    owner_scope = (
        current_user.id
        if "station_owner" in roles and not roles.intersection({"admin", "accountant"})
        else None
    )
    if owner_scope is not None and station_id is not None:
        owns_station = db.query(Station.id).filter(
            Station.id == station_id,
            Station.owner_id == owner_scope,
        ).first()
        if owns_station is None:
            raise HTTPException(status_code=403, detail="Bạn chỉ có thể xem trạm mình sở hữu")
    if station_id is not None:
        lock = find_period_lock(db, station_id, from_date, to_date)
        if lock is not None:
            return get_locked_period_report(lock, status, charge_point_code)
    return get_financial_reconciliation_report(
        db,
        from_date=from_date,
        to_date=to_date,
        station_id=station_id,
        station_owner_id=owner_scope,
        charge_point_code=charge_point_code,
        status=status,
    )


@router.post(
    "/financial/lock",
    dependencies=[Depends(require_role("admin", "accountant", "station_owner"))],
)
def lock_financial_reconciliation_period(
    body: ReconciliationPeriodLockRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    roles = {role.name for role in current_user.roles}
    station_owner_user_id = (
        current_user.id if "station_owner" in roles and not roles.intersection({"admin", "accountant"})
        else None
    )
    try:
        lock, already_locked = close_financial_reconciliation_period(
            db,
            station_id=body.station_id,
            from_date=body.from_date,
            to_date=body.to_date,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            station_owner_user_id=station_owner_user_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    report = get_locked_period_report(lock)
    report["already_locked"] = already_locked
    return report
