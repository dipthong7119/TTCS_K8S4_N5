"""SCRUM-85 financial reconciliation API for accounting reports."""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.station import Station
from app.schemas.reconciliation import (
    ReconciliationPeriodLockRequest,
    ReconciliationPeriodReopenRequest,
)
from app.services.csv_export import csv_response
from app.services.financial_reconciliation import get_financial_reconciliation_report
from app.services.reconciliation_periods import (
    close_financial_reconciliation_period,
    find_period_lock,
    get_latest_period_snapshot,
    get_locked_period_report,
    reopen_financial_reconciliation_period,
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
        if lock is not None and lock.status == "locked":
            return get_locked_period_report(
                lock,
                status,
                charge_point_code,
                snapshot=get_latest_period_snapshot(db, lock),
            )
    return get_financial_reconciliation_report(
        db,
        from_date=from_date,
        to_date=to_date,
        station_id=station_id,
        station_owner_id=owner_scope,
        charge_point_code=charge_point_code,
        status=status,
    )


@router.get(
    "/financial.csv",
    dependencies=[Depends(require_role("admin", "accountant", "station_owner"))],
)
def export_financial_reconciliation_csv(
    current_user: CurrentUser,
    from_date: date = Query(...),
    to_date: date = Query(...),
    station_id: int | None = Query(None, gt=0),
    charge_point_code: str | None = Query(None, min_length=1),
    status: Literal[
        "all", "review", "missing_invoice", "missing_ledger", "amount_mismatch",
        "collection_mismatch", "missing_pricing",
    ] = Query("all"),
    db: Session = Depends(get_db),
):
    """Export the live report or immutable locked snapshot with identical filters."""
    report = get_financial_reconciliation(
        current_user, from_date, to_date, station_id, charge_point_code, status, db
    )
    headers = [
        "row_type", "from_date", "to_date", "session_id", "date", "station_id",
        "station_name", "charge_point_code", "energy_kwh", "expected_vnd", "invoiced_vnd",
        "collected_vnd", "difference_vnd", "invoice_difference_vnd", "issues",
    ]
    summary = report["summary"]
    def rows():
        yield [
            "TOTAL", report["period"]["from_date"], report["period"]["to_date"], "", "", "", "", "",
            f'{summary["total_kwh"]:.3f}', summary["total_expected_vnd"], summary["total_invoiced_vnd"],
            summary["total_collected_vnd"], summary["total_difference_vnd"],
            summary["total_invoice_difference_vnd"], f'review_count={summary["review_count"]}',
        ]
        for item in report["rows"]:
            yield [
                "SESSION", report["period"]["from_date"], report["period"]["to_date"], item["session_id"],
                item["date"], item["station_id"], item["station_name"], item["charge_point_code"],
                f'{item["energy_kwh"]:.3f}', item["expected_vnd"], item["invoiced_vnd"],
                item["collected_vnd"], item["difference_vnd"], item["invoice_difference_vnd"],
                ";".join(item["issues"]),
            ]
    station_suffix = f'-station-{station_id}' if station_id is not None else ""
    return csv_response(
        f'financial-reconciliation-{from_date.isoformat()}-{to_date.isoformat()}{station_suffix}.csv',
        headers,
        rows(),
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
        lock, already_locked, snapshot = close_financial_reconciliation_period(
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
    report = get_locked_period_report(lock, snapshot=snapshot)
    report["already_locked"] = already_locked
    return report


@router.post(
    "/financial/reopen",
    dependencies=[Depends(require_role("admin"))],
)
def reopen_financial_period(
    body: ReconciliationPeriodReopenRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        reopen_financial_reconciliation_period(
            db,
            station_id=body.station_id,
            from_date=body.from_date,
            to_date=body.to_date,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_financial_reconciliation_report(
        db,
        from_date=body.from_date,
        to_date=body.to_date,
        station_id=body.station_id,
        charge_point_code=body.charge_point_code,
        status=body.status,
    )
